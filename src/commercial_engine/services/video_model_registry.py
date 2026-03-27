"""
services/video_model_registry.py
=================================
Multi-Model Video Generation Adapter Registry.

Inspired by Toonflow's architecture, this provides a unified interface for
generating videos across multiple AI platforms:
  - Volcengine/Doubao (火山引擎/豆包 Seedance series)
  - Kling (可灵 v1/v2 series)
  - Vidu (ViduQ1-Q3 series)
  - Wan (万象 wanx/wan2 series)
  - Gemini Veo (veo-2/veo-3 series)

Each adapter follows the pattern:
  1. Submit generation task → get task_id
  2. Poll task status until completed/failed
  3. Return video URL

Usage:
    registry = VideoModelRegistry(config)
    result = await registry.generate(
        model="doubao-seedance-1-5-pro-251215",
        prompt="A cat playing piano",
        duration=8,
        aspect_ratio="16:9"
    )
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)

# ─── Model Capability Registry ─────────────────────────────────────────────

@dataclass
class ModelSpec:
    """Specification for a single video generation model."""
    manufacturer: str       # volcengine, kling, vidu, wan, gemini
    model: str              # model identifier
    durations: list[int]    # supported durations in seconds
    resolutions: list[str]  # supported resolutions (480p, 720p, 1080p)
    aspect_ratios: list[str]   # supported aspect ratios (16:9, 9:16, 1:1)
    types: list[str]        # text, singleImage, startEndRequired, etc.
    audio: bool = False     # whether model generates audio


MODEL_REGISTRY: list[ModelSpec] = [
    # ═══ Volcengine / Doubao Series ═══
    ModelSpec("volcengine", "doubao-seedance-1-5-pro-251215",
             [4,5,6,7,8,9,10,11,12], ["480p","720p","1080p"],
             ["16:9","4:3","1:1","3:4","9:16","21:9"], ["text","endFrameOptional"], audio=True),
    ModelSpec("volcengine", "doubao-seedance-1-0-pro-250528",
             [2,3,4,5,6,7,8,9,10,11,12], ["480p","720p","1080p"],
             ["16:9","4:3","1:1","3:4","9:16","21:9"], ["text","endFrameOptional"]),
    ModelSpec("volcengine", "doubao-seedance-1-0-lite-t2v-250428",
             [2,3,4,5,6,7,8,9,10,11,12], ["480p","720p","1080p"],
             ["16:9","4:3","1:1","3:4","9:16","21:9"], ["text"]),

    # ═══ Kling Series ═══
    ModelSpec("kling", "kling-v2-6(PRO)",
             [5,10], ["1080p"], ["16:9","1:1","9:16"], ["text","startEndRequired"]),
    ModelSpec("kling", "kling-v2-5-turbo(PRO)",
             [5,10], ["1080p"], ["16:9","1:1","9:16"], ["text","startEndRequired"]),
    ModelSpec("kling", "kling-v1-6(PRO)",
             [5,10], ["1080p"], ["16:9","1:1","9:16"], ["text"]),

    # ═══ Vidu Series ═══
    ModelSpec("vidu", "viduq3-pro",
             list(range(1,17)), ["540p","720p","1080p"], [], ["singleImage"], audio=True),
    ModelSpec("vidu", "viduq2-pro",
             list(range(1,11)), ["540p","720p","1080p"], [],
             ["singleImage","reference","startEndRequired"]),

    # ═══ Wan / Wanx Series ═══
    ModelSpec("wan", "wan2.6-t2v",
             list(range(2,16)), ["720p","1080p"],
             ["16:9","9:16","1:1","4:3","3:4"], ["text"], audio=True),
    ModelSpec("wan", "wan2.6-i2v-flash",
             list(range(2,16)), ["720p","1080p"], [], ["singleImage"], audio=True),

    # ═══ Gemini Veo Series ═══
    ModelSpec("gemini", "veo-3.1-generate-preview",
             [4,6,8], ["720p","1080p"], ["16:9","9:16"],
             ["text","singleImage","startEndRequired","endFrameOptional","reference"], audio=True),
    ModelSpec("gemini", "veo-3.0-generate-preview",
             [4,6,8], ["720p","1080p"], ["16:9","9:16"],
             ["text","singleImage"], audio=True),
    ModelSpec("gemini", "veo-2.0-generate-001",
             [5,6,7,8], ["720p"], ["16:9","9:16"], ["text","singleImage"]),
]


@dataclass
class VideoGenResult:
    """Result of a video generation request."""
    success: bool
    video_url: str = ""
    model: str = ""
    manufacturer: str = ""
    duration: float = 0
    error: str = ""
    elapsed_seconds: float = 0


# ─── Adapter Base ───────────────────────────────────────────────────────────

class BaseVideoAdapter:
    """Base class for manufacturer-specific video generation adapters."""

    def __init__(self, api_key: str, base_url: str = ""):
        self.api_key = api_key
        self.base_url = base_url

    async def generate(self, prompt: str, model: str, duration: int,
                       aspect_ratio: str = "16:9", resolution: str = "720p",
                       image_base64: list[str] | None = None,
                       audio: bool = False) -> VideoGenResult:
        raise NotImplementedError

    async def _poll_task(self, poll_fn, interval: float = 5.0,
                         timeout: float = 600) -> str:
        """Generic async task poller. Returns video URL or raises."""
        start = time.time()
        while True:
            if time.time() - start > timeout:
                raise TimeoutError(f"Task timed out after {timeout}s")
            result = await poll_fn()
            if result.get("completed"):
                return result.get("url", "")
            if result.get("error"):
                raise RuntimeError(result["error"])
            await asyncio.sleep(interval)


# ─── Volcengine / Doubao Adapter ────────────────────────────────────────────

class VolcengineAdapter(BaseVideoAdapter):
    """Volcengine Doubao Seedance video generation."""

    async def generate(self, prompt, model, duration, aspect_ratio="16:9",
                       resolution="720p", image_base64=None, audio=False):
        start = time.time()
        base = self.base_url or "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        content = [{"type": "text", "text": prompt}]
        if image_base64:
            for img in image_base64:
                content.append({"type": "image_url", "image_url": {"url": img}, "role": "reference_image"})

        body = {"model": model, "content": content, "duration": duration,
                "resolution": resolution, "watermark": False}
        if audio:
            body["generate_audio"] = True

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(base, headers=headers, json=body) as resp:
                    data = await resp.json()
                    task_id = data.get("id")
                    if not task_id:
                        return VideoGenResult(False, model=model, manufacturer="volcengine",
                                              error=f"Failed to create task: {data}")

                async def poll():
                    async with session.get(f"{base}/{task_id}", headers=headers) as r:
                        d = await r.json()
                        status = d.get("status", "")
                        if status in ("succeeded", "completed"):
                            return {"completed": True, "url": d.get("content", {}).get("video_url")}
                        elif status in ("failed", "cancelled", "expired"):
                            return {"completed": False, "error": f"Task {status}: {d.get('error', '')}"}
                        return {"completed": False}

                video_url = await self._poll_task(poll)
                return VideoGenResult(True, video_url, model, "volcengine",
                                      duration, elapsed_seconds=time.time()-start)
        except Exception as e:
            return VideoGenResult(False, model=model, manufacturer="volcengine", error=str(e))


# ─── Kling Adapter ──────────────────────────────────────────────────────────

class KlingAdapter(BaseVideoAdapter):
    """Kling video generation (可灵)."""

    async def generate(self, prompt, model, duration, aspect_ratio="16:9",
                       resolution="1080p", image_base64=None, audio=False):
        import re
        start = time.time()

        default_base = ("https://api-beijing.klingai.com/v1/videos/image2video|"
                        "https://api-beijing.klingai.com/v1/videos/text2video|"
                        "https://api-beijing.klingai.com/v1/videos/text2video/{taskId}")
        i2v_url, t2v_url, query_url = (self.base_url or default_base).split("|")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        match = re.match(r'^(.+)\((STD|PRO)\)$', model, re.I)
        model_name = match.group(1) if match else model
        mode = match.group(2).lower() if match else "std"

        has_image = bool(image_base64)
        create_url = i2v_url if has_image else t2v_url

        body = {"model_name": model_name, "mode": mode, "duration": str(duration),
                "prompt": prompt, "aspect_ratio": aspect_ratio}
        if has_image:
            strip = lambda s: re.sub(r'^data:image/[^;]+;base64,', '', s)
            body["image"] = strip(image_base64[0])
            if len(image_base64) > 1:
                body["image_tail"] = strip(image_base64[1])

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(create_url, headers=headers, json=body) as resp:
                    data = await resp.json()
                    if data.get("code") != 0:
                        return VideoGenResult(False, model=model, manufacturer="kling",
                                              error=data.get("message", "Unknown"))
                    task_id = data.get("data", {}).get("task_id")

                async def poll():
                    async with session.get(query_url.replace("{taskId}", task_id), headers=headers) as r:
                        d = await r.json()
                        task = d.get("data", {})
                        status = task.get("task_status")
                        if status == "succeed":
                            url = task.get("task_result", {}).get("videos", [{}])[0].get("url")
                            return {"completed": True, "url": url}
                        elif status == "failed":
                            return {"completed": False, "error": task.get("task_status_msg", "")}
                        return {"completed": False}

                video_url = await self._poll_task(poll)
                return VideoGenResult(True, video_url, model, "kling",
                                      duration, elapsed_seconds=time.time()-start)
        except Exception as e:
            return VideoGenResult(False, model=model, manufacturer="kling", error=str(e))


# ─── Wan / Wanx (Alibaba) Adapter ──────────────────────────────────────────

class WanAdapter(BaseVideoAdapter):
    """Wan/Wanx (万象/通义万相) video generation."""

    async def generate(self, prompt, model, duration, aspect_ratio="16:9",
                       resolution="720p", image_base64=None, audio=False):
        start = time.time()
        base = self.base_url or "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/generation"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        body = {
            "model": model,
            "input": {"prompt": prompt},
            "parameters": {"duration": duration, "resolution": resolution,
                           "aspect_ratio": aspect_ratio},
        }
        if image_base64:
            body["input"]["image_url"] = image_base64[0]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(base, headers=headers, json=body) as resp:
                    data = await resp.json()
                    task_id = data.get("output", {}).get("task_id")
                    if not task_id:
                        return VideoGenResult(False, model=model, manufacturer="wan",
                                              error=f"No task_id: {data}")

                task_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

                async def poll():
                    async with aiohttp.ClientSession() as s:
                        async with s.get(task_url, headers={"Authorization": f"Bearer {self.api_key}"}) as r:
                            d = await r.json()
                            status = d.get("output", {}).get("task_status")
                            if status == "SUCCEEDED":
                                url = d.get("output", {}).get("video_url")
                                return {"completed": True, "url": url}
                            elif status == "FAILED":
                                return {"completed": False, "error": d.get("output", {}).get("message", "")}
                            return {"completed": False}

                video_url = await self._poll_task(poll)
                return VideoGenResult(True, video_url, model, "wan",
                                      duration, elapsed_seconds=time.time()-start)
        except Exception as e:
            return VideoGenResult(False, model=model, manufacturer="wan", error=str(e))


# ─── Registry & Router ──────────────────────────────────────────────────────

class VideoModelRegistry:
    """
    Unified multi-model video generation router.

    Usage:
        registry = VideoModelRegistry(config)
        result = await registry.generate(
            model="doubao-seedance-1-5-pro-251215",
            prompt="A cat playing piano",
            duration=8
        )
    """

    ADAPTER_MAP = {
        "volcengine": VolcengineAdapter,
        "kling": KlingAdapter,
        "wan": WanAdapter,
    }

    def __init__(self, config: dict):
        self.config = config
        self._adapters: dict[str, BaseVideoAdapter] = {}
        self._init_adapters()

    def _init_adapters(self):
        """Initialize adapters from config."""
        video_config = self.config.get("video_models", {})
        for manufacturer, adapter_cls in self.ADAPTER_MAP.items():
            mfg_config = video_config.get(manufacturer, {})
            api_key = mfg_config.get("api_key", "")
            base_url = mfg_config.get("base_url", "")
            if api_key:
                self._adapters[manufacturer] = adapter_cls(api_key, base_url)
                logger.info(f"[VideoRegistry] Initialized {manufacturer} adapter")

    def list_models(self, gen_type: str = "text") -> list[ModelSpec]:
        """List available models filtered by generation type."""
        available = []
        for spec in MODEL_REGISTRY:
            if spec.manufacturer in self._adapters and gen_type in spec.types:
                available.append(spec)
        return available

    def find_model(self, model_name: str) -> Optional[ModelSpec]:
        """Find a specific model spec by name."""
        for spec in MODEL_REGISTRY:
            if spec.model == model_name:
                return spec
        return None

    async def generate(self, model: str, prompt: str, duration: int,
                       aspect_ratio: str = "16:9", resolution: str = "720p",
                       image_base64: list[str] | None = None,
                       audio: bool = False) -> VideoGenResult:
        """Generate a video using the specified model."""
        spec = self.find_model(model)
        if not spec:
            return VideoGenResult(False, model=model, error=f"Unknown model: {model}")

        adapter = self._adapters.get(spec.manufacturer)
        if not adapter:
            return VideoGenResult(False, model=model, manufacturer=spec.manufacturer,
                                  error=f"No API key configured for {spec.manufacturer}")

        # Validate duration
        if duration not in spec.durations:
            closest = min(spec.durations, key=lambda d: abs(d - duration))
            logger.warning(f"Duration {duration}s not supported by {model}, using {closest}s")
            duration = closest

        logger.info(f"[VideoRegistry] Generating with {spec.manufacturer}/{model} "
                     f"({duration}s, {resolution}, {aspect_ratio})")
        return await adapter.generate(prompt, model, duration, aspect_ratio,
                                       resolution, image_base64, audio)

    async def auto_select_and_generate(self, prompt: str, duration: int = 8,
                                        aspect_ratio: str = "16:9",
                                        prefer_audio: bool = False) -> VideoGenResult:
        """
        Auto-select the best available model and generate.
        Priority: audio-capable models first if prefer_audio, then by quality tier.
        """
        candidates = self.list_models("text")
        if prefer_audio:
            candidates = [c for c in candidates if c.audio] or candidates

        # Filter by duration support
        candidates = [c for c in candidates if duration in c.durations]

        if not candidates:
            return VideoGenResult(False, error="No suitable model available for the requested parameters")

        # Pick first available (ordered by registry priority)
        best = candidates[0]
        logger.info(f"[VideoRegistry] Auto-selected: {best.manufacturer}/{best.model}")
        return await self.generate(best.model, prompt, duration, aspect_ratio, audio=prefer_audio)
