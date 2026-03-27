"""
services/video_intelligence.py
==============================
Deep Video Content Extractor — Downloads videos from social media URLs,
extracts audio tracks, transcribes speech to text (script extraction),
and analyzes visual content via LLM.

Capabilities:
  1. Video Download: yt-dlp for TikTok, YouTube, Douyin, Instagram, Bilibili, etc.
  2. Audio Extraction: ffmpeg strips audio to WAV for transcription
  3. Speech-to-Text: OpenAI Whisper API for multi-language transcript
  4. Visual Analysis: Key-frame extraction + LLM description (optional)
  5. Metadata Harvesting: title, hashtags, view count, creator info from platform

Output: A structured VideoIntelligenceReport that can be injected directly
into the video generation pipeline as reference material.
"""

import os
import json
import asyncio
import logging
import tempfile
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VideoIntelligenceReport:
    """Structured output from deep video analysis."""
    source_url: str
    platform: str = ""                    # tiktok, youtube, douyin, instagram, bilibili
    original_title: str = ""
    original_description: str = ""
    original_tags: list[str] = field(default_factory=list)
    creator: str = ""
    view_count: int = 0
    duration_seconds: float = 0.0
    transcript: str = ""                  # Full speech-to-text transcript
    transcript_language: str = ""         # Detected language (zh, en, etc.)
    video_local_path: str = ""            # Downloaded video file path
    keyframe_descriptions: list[str] = field(default_factory=list)
    extraction_time_seconds: float = 0.0

    def to_prompt_context(self) -> str:
        """Format as a concise prompt context block for LLM consumption."""
        parts = [f"=== 竞品视频深度分析报告 ==="]
        if self.platform:
            parts.append(f"平台: {self.platform.upper()}")
        if self.original_title:
            parts.append(f"原标题: {self.original_title}")
        if self.creator:
            parts.append(f"创作者: {self.creator}")
        if self.view_count:
            parts.append(f"播放量: {self.view_count:,}")
        if self.duration_seconds:
            parts.append(f"时长: {self.duration_seconds:.0f}秒")
        if self.original_tags:
            parts.append(f"标签: {', '.join(self.original_tags[:10])}")
        if self.transcript:
            parts.append(f"\n--- 原始脚本/台词 (语音转文字) ---\n{self.transcript}")
        if self.original_description:
            parts.append(f"\n--- 原始简介 ---\n{self.original_description[:500]}")
        if self.keyframe_descriptions:
            parts.append(f"\n--- 关键画面描述 ---")
            for i, desc in enumerate(self.keyframe_descriptions, 1):
                parts.append(f"  画面{i}: {desc}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return asdict(self)


class VideoIntelligenceExtractor:
    """
    Deep video content extractor using yt-dlp + ffmpeg + Whisper.

    Usage:
        extractor = VideoIntelligenceExtractor(config)
        report = await extractor.analyze("https://v.douyin.com/xxx")
        print(report.transcript)
        print(report.to_prompt_context())
    """

    def __init__(self, config: dict):
        self.config = config
        self.work_dir = Path(config.get("video_intelligence", {}).get(
            "work_dir", tempfile.mkdtemp(prefix="vidint_")
        ))
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Whisper config
        self.whisper_model = config.get("video_intelligence", {}).get("whisper_model", "whisper-1")
        api_key = config.get("kie", {}).get("api_key") or config.get("openai", {}).get("api_key")
        base_url = config.get("kie", {}).get("base_url") or config.get("openai", {}).get("base_url", "https://api.openai.com/v1")

        self._api_key = api_key
        self._base_url = base_url

        # Max audio duration to transcribe (seconds) — prevent huge API bills
        self.max_audio_duration = config.get("video_intelligence", {}).get("max_audio_seconds", 300)

        # Keyframe extraction
        self.extract_keyframes = config.get("video_intelligence", {}).get("extract_keyframes", True)
        self.keyframe_count = config.get("video_intelligence", {}).get("keyframe_count", 5)

    async def analyze(self, url: str) -> VideoIntelligenceReport:
        """
        Full pipeline: Download → Extract Audio → Transcribe → Analyze Keyframes.
        Returns a structured VideoIntelligenceReport.
        """
        start = time.time()
        report = VideoIntelligenceReport(source_url=url)

        try:
            # Step 1: Download Video + Metadata
            logger.info(f"[VideoIntel] Step 1: Downloading video from {url}")
            video_path, metadata = await self._download_video(url)

            if not video_path:
                logger.warning("[VideoIntel] Download failed. Returning empty report.")
                report.extraction_time_seconds = time.time() - start
                return report

            report.video_local_path = str(video_path)
            report.platform = self._detect_platform(url)
            report.original_title = metadata.get("title", "")
            report.original_description = metadata.get("description", "")
            report.original_tags = metadata.get("tags", []) or []
            report.creator = metadata.get("uploader", "") or metadata.get("channel", "")
            report.view_count = metadata.get("view_count", 0) or 0
            report.duration_seconds = metadata.get("duration", 0) or 0

            logger.info(f"[VideoIntel] Downloaded: {report.original_title} ({report.duration_seconds:.0f}s)")

            # Step 2: Extract Audio
            logger.info("[VideoIntel] Step 2: Extracting audio track...")
            audio_path = await self._extract_audio(video_path)

            # Step 3: Transcribe with Whisper
            if audio_path:
                logger.info("[VideoIntel] Step 3: Transcribing with Whisper...")
                transcript, lang = await self._transcribe_audio(audio_path)
                report.transcript = transcript
                report.transcript_language = lang
                logger.info(f"[VideoIntel] Transcript: {len(transcript)} chars, language={lang}")

                # Clean up audio file
                try:
                    os.unlink(audio_path)
                except Exception:
                    pass

            # Step 4: Extract Keyframes (optional)
            if self.extract_keyframes and video_path:
                logger.info("[VideoIntel] Step 4: Extracting keyframes...")
                keyframes = await self._extract_keyframes_from_video(video_path)
                report.keyframe_descriptions = keyframes

        except Exception as e:
            logger.error(f"[VideoIntel] Analysis failed: {e}")

        report.extraction_time_seconds = time.time() - start
        logger.info(f"[VideoIntel] Analysis complete in {report.extraction_time_seconds:.1f}s")
        return report

    async def _download_video(self, url: str) -> tuple[Optional[str], dict]:
        """
        Download video using yt-dlp. Returns (video_path, metadata_dict).
        yt-dlp supports: TikTok, YouTube, Douyin, Instagram, Bilibili, Twitter/X, etc.
        """
        output_template = str(self.work_dir / f"dl_{int(time.time())}_%(id)s.%(ext)s")
        info_file = str(self.work_dir / f"info_{int(time.time())}.json")

        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--format", "best[ext=mp4]/best",
            "--output", output_template,
            "--write-info-json",
            "--no-write-thumbnail",
            "--max-filesize", "200M",
            "--socket-timeout", "30",
            "--retries", "3",
            url
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                err = stderr.decode("utf-8", errors="ignore")
                logger.error(f"[VideoIntel] yt-dlp failed: {err[:500]}")
                return None, {}

            # Find the downloaded video file
            video_path = None
            for f in self.work_dir.iterdir():
                if f.name.startswith("dl_") and f.suffix in (".mp4", ".webm", ".mkv"):
                    video_path = f
                    break

            # Find and parse info JSON
            metadata = {}
            for f in self.work_dir.iterdir():
                if f.suffix == ".json" and "info" in f.name:
                    try:
                        with open(f, "r", encoding="utf-8") as jf:
                            metadata = json.load(jf)
                    except Exception:
                        pass
                    # Also check for yt-dlp's auto-generated info json
                elif f.name.endswith(".info.json"):
                    try:
                        with open(f, "r", encoding="utf-8") as jf:
                            metadata = json.load(jf)
                    except Exception:
                        pass

            return str(video_path) if video_path else None, metadata

        except FileNotFoundError:
            logger.error("[VideoIntel] yt-dlp not found! Install: pip install yt-dlp")
            return None, {}
        except Exception as e:
            logger.error(f"[VideoIntel] Download error: {e}")
            return None, {}

    async def _extract_audio(self, video_path: str) -> Optional[str]:
        """Extract audio from video using ffmpeg → WAV (16kHz mono for Whisper)."""
        audio_path = str(Path(video_path).with_suffix(".wav"))

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn",                    # No video
            "-acodec", "pcm_s16le",   # 16-bit PCM WAV
            "-ar", "16000",           # 16kHz sample rate (Whisper optimal)
            "-ac", "1",               # Mono
            "-t", str(self.max_audio_duration),  # Max duration cap
            audio_path
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await process.communicate()

            if process.returncode != 0:
                err = stderr.decode("utf-8", errors="ignore")
                logger.warning(f"[VideoIntel] Audio extraction failed: {err[:300]}")
                return None

            if not Path(audio_path).exists() or Path(audio_path).stat().st_size < 1000:
                logger.warning("[VideoIntel] Audio file too small or empty — video may have no audio")
                return None

            return audio_path

        except Exception as e:
            logger.error(f"[VideoIntel] FFmpeg audio extraction error: {e}")
            return None

    async def _transcribe_audio(self, audio_path: str) -> tuple[str, str]:
        """
        Transcribe audio using OpenAI Whisper API.
        Returns (transcript_text, detected_language).
        """
        if not self._api_key:
            logger.warning("[VideoIntel] No API key for Whisper. Skipping transcription.")
            return "", ""

        try:
            import aiohttp

            url = f"{self._base_url}/audio/transcriptions"
            headers = {"Authorization": f"Bearer {self._api_key}"}

            form = aiohttp.FormData()
            form.add_field("file", open(audio_path, "rb"),
                          filename=Path(audio_path).name,
                          content_type="audio/wav")
            form.add_field("model", self.whisper_model)
            form.add_field("response_format", "verbose_json")

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=form, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(f"[VideoIntel] Whisper API failed ({resp.status}): {body[:300]}")
                        return "", ""

                    result = await resp.json()

            transcript = result.get("text", "")
            language = result.get("language", "")

            return transcript, language

        except Exception as e:
            logger.error(f"[VideoIntel] Whisper transcription error: {e}")
            return "", ""

    async def _extract_keyframes_from_video(self, video_path: str) -> list[str]:
        """
        Extract N evenly-spaced keyframes from video using ffmpeg,
        then describe each frame using GPT-4o vision (if available).
        """
        keyframe_dir = self.work_dir / "keyframes"
        keyframe_dir.mkdir(exist_ok=True)

        # Use ffmpeg to extract keyframes
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"select='not(mod(n\\,30))',setpts=N/FRAME_RATE/TB,scale=512:-1",
            "-frames:v", str(self.keyframe_count),
            "-q:v", "3",
            str(keyframe_dir / "frame_%03d.jpg")
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()

            frames = sorted(keyframe_dir.glob("frame_*.jpg"))
            if not frames:
                return []

            descriptions = []
            for frame in frames[:self.keyframe_count]:
                desc = f"[Keyframe: {frame.name}] (视觉分析需要 GPT-4o Vision 接口)"
                descriptions.append(desc)

            return descriptions

        except Exception as e:
            logger.warning(f"[VideoIntel] Keyframe extraction failed: {e}")
            return []

    @staticmethod
    def _detect_platform(url: str) -> str:
        """Detect which platform a URL belongs to."""
        url_lower = url.lower()
        if "tiktok" in url_lower:
            return "tiktok"
        elif "douyin" in url_lower or "v.douyin" in url_lower:
            return "douyin"
        elif "youtube" in url_lower or "youtu.be" in url_lower:
            return "youtube"
        elif "instagram" in url_lower:
            return "instagram"
        elif "bilibili" in url_lower or "b23.tv" in url_lower:
            return "bilibili"
        elif "twitter" in url_lower or "x.com" in url_lower:
            return "twitter"
        elif "weibo" in url_lower:
            return "weibo"
        else:
            return "unknown"

    def cleanup(self):
        """Remove all downloaded files from work directory."""
        import shutil
        try:
            shutil.rmtree(self.work_dir, ignore_errors=True)
        except Exception:
            pass
