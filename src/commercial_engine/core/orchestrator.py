"""
core/orchestrator.py
====================
Main pipeline controller for UGC Video Pro.

v3.0 — Director Agent Edition
    The orchestrator now delegates decision-making to the DirectorAgent
    (GPT 5.2 via KIE.AI Chat API) which acts as a "film director":
    - Analyzes product → chooses model → plans segments → budgets costs
    - Then delegates execution back to the deterministic pipeline

    Legacy mode (director disabled) still works as before.

Pipeline stages:
    1. Director plans production (model, segments, budget)  [NEW]
    2. Analyze product image (Gemini Vision)
    3. Extract URL content (if URL mode)
    4. Generate AI script (via ScriptGenerator)
    5. Frame chain generation (FrameChainer) — THE MOST CRITICAL STEP
    6. Stitch all clips (VideoStitcher + FFmpeg)
    7. Multi-language TTS generation (parallel)              [NEW]
    8. Upload to Google Drive (optional)
    9. Return VideoResult

This class is stateless — each call to generate() is independent.
"""

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from core.frame_chainer import FrameChainer
from core.script_generator import ScriptGenerator
from core.video_stitcher import VideoStitcher
from models import get_model_adapter
from services.google_drive import GoogleDriveUploader
from services.image_analyzer import ImageAnalyzer
from services.url_extractor import URLExtractor
from services.publisher import TikTokPublisher, YouTubeShortsPublisher, DouyinPublisher, InstagramReelsPublisher
from services.viral_copywriter import ViralCopywriter
from services.bgm_matcher import AIBGMMatcher
from services.video_intelligence import VideoIntelligenceExtractor
from services.video_model_registry import VideoModelRegistry
from utils.logger import get_logger

logger = get_logger(__name__)


class PipelineExecutionError(Exception):
    """Raised when a critical pipeline step fails."""
    pass


class ContextPreparationError(PipelineExecutionError):
    pass


class ScriptGenerationError(PipelineExecutionError):
    pass


class VideoGenerationError(PipelineExecutionError):
    pass


@dataclass
class VideoRequest:
    """Input parameters for a video generation job."""
    user_id: int
    chat_id: int
    mode: str
    model: str
    duration: int
    language: str
    text_prompt: str = ""
    image_path: Optional[str] = None
    url: Optional[str] = None
    url_content: Optional[str] = None
    num_segments: int = 0
    aspect_ratio: str = "9:16"
    quality_tier: str = "economy"   # NEW: economy | premium | china
    num_images: int = 1             # NEW: number of uploaded images


@dataclass
class VideoResult:
    """Result of a completed video generation pipeline."""
    video_path: str
    drive_link: Optional[str]
    duration: int
    num_segments: int
    model: str
    elapsed_seconds: float
    segment_paths: list[str] = field(default_factory=list)
    script_json: str = ""
    product_analysis: dict = field(default_factory=dict)
    # Director Agent metadata
    director_decisions: list[str] = field(default_factory=list)
    production_plan_json: str = ""
    estimated_cost_usd: float = 0.0
    tts_paths: dict = field(default_factory=dict)
    # Publishing results
    publish_results: list[dict] = field(default_factory=list)
    viral_metadata: dict = field(default_factory=dict)
    # Storyboard data
    storyboard: dict = field(default_factory=dict)


class VideoOrchestrator:
    """
    Orchestrates the full UGC video generation pipeline.

    v3.0: Now powered by DirectorAgent for intelligent decision-making.
    Falls back to legacy hardcoded logic if Director is unavailable.
    """

    def __init__(self, config: dict):
        self.config = config
        self.output_dir = Path(config.get("video", {}).get("output_dir", "/tmp/ugc_videos"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Core pipeline modules
        self.image_analyzer = ImageAnalyzer(config)
        self.url_extractor = URLExtractor(config)
        self.video_intel = VideoIntelligenceExtractor(config)
        self.script_generator = ScriptGenerator(config)
        self.frame_chainer = FrameChainer(config)
        self.video_stitcher = VideoStitcher(config)

        # Google Drive uploader
        drive_config = config.get("google_drive", {})
        self.drive_uploader = GoogleDriveUploader(config) if drive_config.get("credentials_path") else None

        # Social Media Publishers
        self.publishers = []
        publisher_config = config.get("publisher", {})
        if publisher_config.get("enable_tiktok"):
            self.publishers.append(TikTokPublisher(config))
        if publisher_config.get("enable_youtube_shorts"):
            self.publishers.append(YouTubeShortsPublisher(config))
        if publisher_config.get("enable_douyin"):
            self.publishers.append(DouyinPublisher(config))
        if publisher_config.get("enable_instagram_reels"):
            self.publishers.append(InstagramReelsPublisher(config))

        # Viral Copywriter Agent
        viral_config = config.get("viral_copywriter", {})
        self.viral_copywriter = ViralCopywriter(config) if viral_config.get("enabled", True) else None

        # BGM Matcher Agent
        bgm_config = config.get("bgm_matcher", {})
        self.bgm_matcher = AIBGMMatcher(config) if bgm_config.get("enabled", True) else None

        # Multi-Model Video Registry
        self.video_registry = VideoModelRegistry(config)

        # AI Storyboard Agent (Deprecated, moved to DirectorAgent)
        storyboard_config = config.get("storyboard", {})
        self.storyboard_agent = None

        # Director Agent
        self._director = None
        self._director_enabled = self._check_director_enabled(config)
        if self._director_enabled:
            try:
                from core.director_agent import DirectorAgent
                self._director = DirectorAgent(config)
                logger.info("Director Agent initialized (GPT 5.2 via KIE.AI)")
            except Exception as e:
                logger.warning(f"Director Agent init failed: {e} — using legacy mode")
                self._director_enabled = False

    def _check_director_enabled(self, config: dict) -> bool:
        kie_key = config.get("kie", {}).get("api_key", "")
        if not kie_key:
            return False
        return config.get("director", {}).get("enabled", True)

    async def generate(
        self,
        request: VideoRequest,
        progress_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
    ) -> VideoResult:
        if self.storyboard_agent:
            return await self._generate_with_storyboard(request, progress_callback, status_callback)
        if self._director_enabled and self._director:
            return await self._generate_with_director(request, progress_callback, status_callback)
        return await self._generate_legacy(request, progress_callback, status_callback)

    # ══════════════════════════════════════════════════════════
    # Additional Storyboard Pipeline Path
    # ══════════════════════════════════════════════════════════

    async def _generate_with_storyboard(
        self,
        request: VideoRequest,
        progress_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
    ) -> VideoResult:
        start_time = time.time()
        logger.info(f"[Storyboard Mode] Starting pipeline for user={request.user_id}")
        
        try:
            import json
            product_analysis, url_content = await self._prepare_context(request, status_callback)
            
            await self._update_status(status_callback, "storyboard_planning")
            
            context_text = f"Prompt: {request.text_prompt}\nProduct: {product_analysis}\nURL Content: {url_content}"
            
            episode = await self.storyboard_agent.generate_episode(
                script_text=context_text,
                title=getattr(request, 'text_prompt', 'AI Storyboard Video')[:50],
                style="ugc"
            )
            
            if not getattr(episode, "shots", []):
                raise ScriptGenerationError("Storyboard Agent returned empty shots array.")
                
            model_key = request.model if request.model and request.model != "auto" else "doubao-seedance-1-5-pro-251215"
            segment_paths = []
            total_duration = 0
            
            for i, shot in enumerate(episode.shots):
                await self._update_status(status_callback, "generating_shot", shot_index=i+1, total=len(episode.shots))
                
                output_filename = f"Storyboard_{request.mode}_{model_key}_{int(time.time())}_{i}.mp4"
                output_path = str(self.output_dir / output_filename)
                
                prompt = f"{shot.prompt}. Camera: {shot.camera_movement}"
                
                result = await self.video_registry.generate(
                    model=model_key,
                    prompt=prompt,
                    duration=int(shot.duration_seconds),
                    aspect_ratio=request.aspect_ratio,
                    audio=False
                )
                
                if not result.success:
                    raise VideoGenerationError(f"Storyboard shot generation failed: {result.error}")
                
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(result.video_url) as resp:
                        if resp.status != 200:
                            raise VideoGenerationError(f"Failed to download generated shot ({resp.status})")
                        with open(output_path, "wb") as f:
                            f.write(await resp.read())
                            
                segment_paths.append(output_path)
                total_duration += shot.duration_seconds

            await self._update_status(status_callback, "stitching", count=len(segment_paths))
            
            output_filename = f"UGC_{request.mode}_{model_key}_{int(total_duration)}s_{int(time.time())}.mp4"
            final_path = str(self.output_dir / output_filename)
            final_path = await self.video_stitcher.stitch(
                video_paths=segment_paths,
                output_path=final_path,
            )

            # mock the script object for post_production to succeed
            class _DummyScript:
                def __init__(self, raw_json):
                    self.raw_json = raw_json
            dummy_script = _DummyScript(json.dumps(episode.to_dict(), ensure_ascii=False) if hasattr(episode, 'to_dict') else "")

            final_path, drive_link, metadata_out, publish_results = await self._post_production(
                request, final_path, dummy_script, status_callback
            )

        except Exception as e:
            logger.error(f"[Storyboard Mode] Pipeline execution failed: {e}")
            raise PipelineExecutionError(f"Storyboard mode generation failed: {e}") from e
        
        finally:
            self._cleanup_segments(locals().get("segment_paths", []), locals().get("final_path", None))
        
        elapsed = time.time() - start_time
        return VideoResult(
            video_path=final_path,
            drive_link=drive_link,
            duration=int(total_duration),
            num_segments=len(episode.shots),
            model=model_key,
            elapsed_seconds=elapsed,
            segment_paths=segment_paths,
            script_json=json.dumps(episode.to_dict(), ensure_ascii=False) if hasattr(episode, "to_dict") else "",
            product_analysis=product_analysis,
            production_plan_json=episode.to_markdown(),
            storyboard=episode.to_dict() if hasattr(episode, "to_dict") else {},
            publish_results=publish_results,
            viral_metadata=metadata_out,
        )

    # ══════════════════════════════════════════════════════════
    # Atomic Execution Blocks
    # ══════════════════════════════════════════════════════════

    async def _update_status(self, callback: Optional[Callable], key: str, **kwargs):
        if callback:
            await callback(key, **kwargs)

    async def _prepare_context(self, request: VideoRequest, status_callback: Optional[Callable] = None) -> tuple[dict, Optional[str]]:
        """Analyzes image and extracts URL content to build context for generation."""
        product_analysis = {}
        if request.image_path and Path(request.image_path).exists():
            await self._update_status(status_callback, "analyzing_image")
            try:
                product_analysis = await self.image_analyzer.analyze(request.image_path)
                logger.info(f"Image analyzed: {product_analysis.get('type', 'unknown')}")
            except Exception as e:
                raise ContextPreparationError(f"Image analysis failed: {e}") from e

        if request.text_prompt:
            product_analysis["user_description"] = request.text_prompt

        url_content = request.url_content
        if request.url and not url_content:
            await self._update_status(status_callback, "extracting_url")
            try:
                platform = VideoIntelligenceExtractor._detect_platform(request.url)
                if platform != "unknown":
                    logger.info(f"Detected video platform: {platform}. Using deep extraction...")
                    await self._update_status(status_callback, "deep_video_analysis")
                    intel_report = await self.video_intel.analyze(request.url)
                    url_content = intel_report.to_prompt_context()
                    logger.info(f"Deep extraction complete: {len(intel_report.transcript)} chars")
                else:
                    url_content = await self.url_extractor.extract(request.url)
            except Exception as e:
                raise ContextPreparationError(f"URL extraction failed: {e}") from e

        return product_analysis, url_content

    async def _generate_script(
        self,
        request: VideoRequest,
        product_analysis: dict,
        url_content: Optional[str],
        model_key: str,
        segment_durations: list[int],
        status_callback: Optional[Callable] = None,
    ):
        """Generates video script using the configured models."""
        await self._update_status(status_callback, "generating_script", segments=len(segment_durations))
        try:
            script = await self.script_generator.generate_script(
                product_analysis=product_analysis,
                segment_durations=segment_durations,
                model_key=model_key,
                language=request.language,
                url_content=url_content,
                aspect_ratio=request.aspect_ratio,
            )
            logger.info(f"Script ready: {script.num_segments} scenes")
            return script
        except Exception as e:
            raise ScriptGenerationError(f"Failed to generate script: {e}") from e

    async def _generate_and_stitch_video(
        self,
        request: VideoRequest,
        script,
        model_adapter,
        progress_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
    ) -> tuple[str, list[str]]:
        """Handles frame chaining and video stitching."""
        
        async def poll_cb(attempt: int, max_retries: int):
            await self._update_status(
                status_callback,
                "polling",
                model=model_adapter.model_key.upper().replace("_", " "),
                attempt=attempt,
                max_retries=max_retries,
            )

        try:
            segment_paths = await self.frame_chainer.chain_segments(
                script=script,
                model_adapter=model_adapter,
                reference_image=request.image_path,
                aspect_ratio=request.aspect_ratio,
                progress_callback=progress_callback,
                poll_callback=poll_cb,
            )
            logger.info(f"Frame chain complete: {len(segment_paths)} clips")
        except Exception as e:
            raise VideoGenerationError(f"Frame chaining failed: {e}") from e

        await self._update_status(status_callback, "stitching", count=len(segment_paths))
        try:
            output_filename = f"UGC_{request.mode}_{model_adapter.model_key}_{request.duration}s_{int(time.time())}.mp4"
            output_path = str(self.output_dir / output_filename)
            final_path = await self.video_stitcher.stitch(
                video_paths=segment_paths,
                output_path=output_path,
            )
        except Exception as e:
            logger.error(f"Stitching failed: {e}")
            if segment_paths:
                logger.warning("Returning first clip due to stitching failure")
                final_path = segment_paths[0]
            else:
                raise VideoGenerationError(f"Video stitching failed explicitly and no segments are available: {e}") from e
                
        return final_path, segment_paths

    async def _post_production(
        self, 
        request: VideoRequest, 
        final_path: str, 
        script, 
        status_callback: Optional[Callable] = None,
    ) -> tuple[str, Optional[str], dict, list[dict]]:
        """Applies TTS/BGM, uploads to Drive, creates viral copy and publishes."""
        
        context = script.raw_json if hasattr(script, 'raw_json') else str(request.text_prompt)

        # 1. Background Music
        if self.bgm_matcher:
            await self._update_status(status_callback, "adding_bgm")
            try:
                final_path = await self.bgm_matcher.add_bgm(final_path, context)
            except Exception as e:
                logger.warning(f"BGM Matcher failed, skipping BGM: {e}")

        # 2. Upload to Google Drive (optional)
        drive_link = None
        if self.drive_uploader:
            await self._update_status(status_callback, "uploading_drive")
            try:
                drive_link = await self.drive_uploader.upload(
                    file_path=final_path,
                    folder_name=self.config.get("google_drive", {}).get("folder_name", "UGC_Videos"),
                )
                logger.info(f"Uploaded to Google Drive: {drive_link}")
            except Exception as e:
                logger.warning(f"Google Drive upload failed: {e}")
                await self._update_status(status_callback, "error_drive_upload")

        # 3. Viral Copywriting 
        metadata = {
            "title": getattr(request, 'text_prompt', 'AI Generated Video')[:50],
            "description": context,
            "tags": ["ai", "generated", request.mode]
        }
        
        if self.viral_copywriter:
            await self._update_status(status_callback, "generating_viral_copy")
            try:
                viral_data = await self.viral_copywriter.generate_content(context[:1500])
                tags = viral_data.get("tags", metadata["tags"])
                metadata.update({
                    "title": viral_data.get("title", metadata["title"]),
                    "description": viral_data.get("description", metadata["description"]),
                    "tags": [t.strip() for t in str(tags).split(",")] if not isinstance(tags, list) else tags
                })
                logger.info(f"[ViralCopy] Generated Title: {metadata['title']}")
            except Exception as e:
                logger.warning(f"Viral copy generation failed, using defaults: {e}")

        # 4. Multi-Platform Publishing (TikTok, YouTube, Douyin, IG)
        publish_results = []
        for publisher in self.publishers:
            pub_name = publisher.__class__.__name__.replace("Publisher", "")
            await self._update_status(status_callback, f"publishing_{pub_name.lower()}")
            try:
                res = await publisher.publish(final_path, metadata)
                publish_results.append(res)
                logger.info(f"Published to {res.get('platform', 'unknown')}: {res.get('status', 'unknown')}")
            except Exception as e:
                logger.error(f"Publishing component failed: {e}")
                publish_results.append({"platform": pub_name.lower(), "status": "failed", "error": str(e)})

        return final_path, drive_link, metadata, publish_results

    # ══════════════════════════════════════════════════════════
    # Execution Pathways
    # ══════════════════════════════════════════════════════════

    async def _generate_with_director(
        self,
        request: VideoRequest,
        progress_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
    ) -> VideoResult:
        start_time = time.time()
        logger.info(f"[Director Mode] Starting pipeline for user={request.user_id}")
        
        try:
            product_analysis, url_content = await self._prepare_context(request, status_callback)
            
            await self._update_status(status_callback, "director_planning")
            plan = await self._director.create_production_plan(
                product_analysis=product_analysis,
                duration=request.duration,
                language=request.language,
                quality_tier=request.quality_tier,
                url_content=url_content,
                user_model_override=request.model if request.model != "auto" else None,
                num_images=request.num_images,
            )
            
            effective_model = plan.video_model
            model_adapter = get_model_adapter(effective_model, self.config)
            
            script = await self._generate_script(
                request, product_analysis, url_content, effective_model, plan.segment_durations, status_callback
            )
            
            final_path, segment_paths = await self._generate_and_stitch_video(
                request, script, model_adapter, progress_callback, status_callback
            )
            
            tts_paths = {}
            if plan.tts_languages:
                await self._update_status(status_callback, "generating_tts")
                tts_paths = await self._director._generate_multilang_tts(
                    script=script, languages=plan.tts_languages, config=self.config
                )

            final_path, drive_link, metadata, publish_results = await self._post_production(
                request, final_path, script, status_callback
            )

        except Exception as e:
            logger.error(f"[Director Mode] Pipeline execution failed: {e}")
            raise PipelineExecutionError(f"Director mode generation failed: {e}") from e
        
        finally:
            self._cleanup_segments(locals().get("segment_paths", []), locals().get("final_path", None))
        
        elapsed = time.time() - start_time
        return VideoResult(
            video_path=final_path,
            drive_link=drive_link,
            duration=request.duration,
            num_segments=plan.num_segments,
            model=effective_model,
            elapsed_seconds=elapsed,
            segment_paths=segment_paths,
            script_json=script.raw_json,
            product_analysis=product_analysis,
            director_decisions=self._director._decisions,
            production_plan_json=plan.raw_json,
            estimated_cost_usd=plan.estimated_cost_usd,
            tts_paths=tts_paths,
            publish_results=publish_results,
            viral_metadata=metadata,
        )

    async def _generate_legacy(
        self,
        request: VideoRequest,
        progress_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
    ) -> VideoResult:
        start_time = time.time()
        logger.info(f"[Legacy Mode] Starting pipeline for user={request.user_id}")
        
        try:
            model_adapter = get_model_adapter(request.model, self.config)
            segment_durations = model_adapter.calculate_segments(request.duration)
            
            product_analysis, url_content = await self._prepare_context(request, status_callback)
            
            script = await self._generate_script(
                request, product_analysis, url_content, request.model, segment_durations, status_callback
            )
            
            final_path, segment_paths = await self._generate_and_stitch_video(
                request, script, model_adapter, progress_callback, status_callback
            )
            
            final_path, drive_link, metadata, publish_results = await self._post_production(
                request, final_path, script, status_callback
            )
            
        except Exception as e:
            logger.error(f"[Legacy Mode] Pipeline execution failed: {e}")
            raise PipelineExecutionError(f"Legacy mode generation failed: {e}") from e
            
        finally:
            self._cleanup_segments(locals().get("segment_paths", []), locals().get("final_path", None))

        elapsed = time.time() - start_time
        return VideoResult(
            video_path=final_path,
            drive_link=drive_link,
            duration=request.duration,
            num_segments=len(segment_durations),
            model=request.model,
            elapsed_seconds=elapsed,
            segment_paths=segment_paths,
            script_json=script.raw_json,
            product_analysis=product_analysis,
            publish_results=publish_results,
            viral_metadata=metadata,
        )

    def _cleanup_segments(self, segment_paths: list[str], final_path: Optional[str]):
        """Cleans up individual video segments if there are multiple."""
        if len(segment_paths) > 1:
            for path in segment_paths:
                if path != final_path:
                    try:
                        if Path(path).exists():
                            os.unlink(path)
                    except Exception:
                        pass


# ─── Health Check API ────────

def get_system_status() -> dict:
    return {"status": "OK", "uptime": "active"}

def get_registered_models() -> list[str]:
    try:
        from core.model_router import MODEL_REGISTRY
        return list(MODEL_REGISTRY.keys())
    except Exception as e:
        import logging
        logging.error(f"[HealthCheck] Failed to load MODEL_REGISTRY: {e}")
        return []

def get_pipeline_availability() -> dict:
    return {
        "ugc_video": "operational",
        "animation": "operational",
        "engineering": "operational",
    }

def get_health_status() -> dict:
    try:
        return {
            "system_status": get_system_status(),
            "registered_models": get_registered_models(),
            "pipeline_availability": get_pipeline_availability(),
        }
    except Exception as e:
        return {"error": str(e)}


# ─── Multi-Language Subtitle Processing ──

async def process_video_with_subtitles(
    video_path: str,
    tts_outputs: dict[str, str],
    output_path: str,
    config: dict | None = None,
) -> str:
    """Burn multi-language subtitles into video via FFmpeg."""
    import logging
    from pathlib import Path as _Path
    from utils.ffmpeg_tools import FFmpegTools

    logging.basicConfig(level=logging.INFO)
    _config = config or {}
    ffmpeg = FFmpegTools(_config)
    subtitle_paths: list[str] = []

    for language, tts_text in tts_outputs.items():
        try:
            lines = tts_text.strip().split("\n")
            srt_lines: list[str] = []
            idx = 1
            for line in lines:
                parts = line.split(",", 2)
                if len(parts) == 3:
                    start, end, text = parts
                    srt_lines.append(str(idx))
                    srt_lines.append(f"{start.strip()} --> {end.strip()}")
                    srt_lines.append(text.strip())
                    srt_lines.append("")
                    idx += 1

            sub_path = str(_Path(output_path).parent / f"subtitles_{language}.srt")
            with open(sub_path, "w", encoding="utf-8") as f:
                f.write("\n".join(srt_lines))
            subtitle_paths.append(sub_path)
        except Exception as e:
            logging.error(f"Failed to process subtitles for {language}: {e}")

    if subtitle_paths:
        def escape_ffmpeg_path(p: str) -> str:
            p = p.replace('\\', '/')
            p = p.replace(':', '\\\\:')
            return f"\\'{p}\\'"

        sub_filter = ",".join([f"subtitles={escape_ffmpeg_path(sp)}" for sp in subtitle_paths])
        cmd = [
            "ffmpeg", "-y", "-i", video_path, "-vf", sub_filter,
            "-c:a", "copy", output_path
        ]
        try:
            import subprocess
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return output_path
        except subprocess.CalledProcessError as e:
            logging.error(f"FFmpeg subtitle burning failed: {e.stderr.decode()}")
            return video_path
    
    return video_path
