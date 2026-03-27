"""
services/bgm_matcher.py
========================
AI-powered Background Music Matcher.

Analyzes video script mood via LLM, selects matching BGM from inventory,
and mixes it into the video using FFmpeg with configurable volume.

Supports:
  - Expanded mood library (9+ moods)
  - Configurable BGM volume (via config or per-call)
  - Dynamic volume adjustment (ducks BGM during speech sections)
  - Async FFmpeg execution to avoid blocking
"""

import os
import json
import re
import asyncio
import logging
from pathlib import Path
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class AIBGMMatcher:
    """
    Matches background music to video scripts using AI mood analysis.

    Config keys (under 'bgm_matcher'):
      - model: LLM model for mood analysis (default: gpt-4o-mini)
      - bgm_dir: path to BGM asset directory (default: assets/music)
      - default_volume: BGM volume 0.0-1.0 (default: 0.12)
      - duck_volume: volume when speech is detected (default: 0.06)
      - enabled: whether to enable BGM (default: true)
    """

    MOOD_INVENTORY = {
        "happy":        "happy_tune.mp3",
        "sad":          "sad_melody.mp3",
        "exciting":     "epic_beat.mp3",
        "relaxed":      "chill_lofi.mp3",
        "mysterious":   "dark_synth.mp3",
        "romantic":     "love_ballad.mp3",
        "tense":        "suspense_drone.mp3",
        "inspirational": "uplifting_piano.mp3",
        "comedic":      "quirky_fun.mp3",
    }

    VALID_MOODS = list(MOOD_INVENTORY.keys())

    def __init__(self, config: dict):
        self.config = config

        # API credentials
        api_key = config.get("kie", {}).get("api_key") or config.get("openai", {}).get("api_key")
        base_url = config.get("kie", {}).get("base_url") or config.get("openai", {}).get("base_url", "https://api.openai.com/v1")
        bgm_cfg = config.get("bgm_matcher", {})
        self.model = bgm_cfg.get("model", "gpt-4o-mini")

        self.llm_client = AsyncOpenAI(api_key=api_key or "missing", base_url=base_url)

        # BGM config
        self.music_dir = Path(bgm_cfg.get("bgm_dir", config.get("bgm_dir", "assets/music")))
        self.default_volume = bgm_cfg.get("default_volume", 0.12)
        self.duck_volume = bgm_cfg.get("duck_volume", 0.06)

    async def analyze_script(self, script_context: str) -> str:
        """Analyze script to determine dominant emotional mood."""
        moods_str = ", ".join(self.VALID_MOODS)
        prompt = (
            f"Analyze the following video script and determine its core emotional mood. "
            f"You must categorize it exactly into one of these moods: [{moods_str}].\n\n"
            f"SCRIPT:\n{script_context[:1000]}\n\n"
            f"Return ONLY valid JSON with exactly one key: 'mood'."
        )

        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a musical emotion analyzer. Return JSON only."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            raw = response.choices[0].message.content.strip()
            cleaned = re.sub(r'^```(?:json)?\s*', '', raw)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            data = json.loads(cleaned)
            mood = data.get("mood", "happy").lower().strip()

            if mood not in self.VALID_MOODS:
                logger.warning(f"[BGM] LLM returned invalid mood '{mood}', defaulting to 'happy'")
                mood = "happy"

            return mood
        except Exception as e:
            logger.warning(f"[BGM] Mood analysis failed: {e}. Defaulting to 'happy'.")
            return "happy"

    async def _run_ffmpeg_mix(self, video_path: str, bgm_file: str,
                              output_path: str, volume: float = 0.12,
                              has_speech: bool = True):
        """
        Mix BGM into video using FFmpeg.

        If has_speech is True, uses sidechaincompress to automatically duck
        BGM volume when speech is detected. Otherwise uses static volume.
        """
        logger.info(f"[BGM] Mixing video with BGM (vol={volume}, speech_duck={has_speech})")

        if has_speech:
            # Dynamic ducking: lower BGM volume when speech audio is present
            filter_complex = (
                f"[1:a]volume={volume}[bgm];"
                f"[0:a][bgm]sidechaincompress=threshold=0.02:ratio=6:attack=200:release=1000[aout]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-i", str(bgm_file),
                "-filter_complex", filter_complex,
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-shortest",
                str(output_path)
            ]
        else:
            # Static volume mix (no speech track)
            filter_complex = (
                f"[1:a]volume={volume}[a1];"
                f"[0:a][a1]amix=inputs=2:duration=first"
            )
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-i", str(bgm_file),
                "-filter_complex", filter_complex,
                "-c:v", "copy",
                str(output_path)
            ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode('utf-8', errors='ignore')[-500:]
            raise RuntimeError(f"FFmpeg mixing failed (exit {process.returncode}): {error_msg}")

    async def add_bgm(self, video_path: str, script_context: str,
                      volume: float | None = None,
                      has_speech: bool = True) -> str:
        """
        Main entry: analyze mood → pick music → mix into video.

        :param video_path: Path to input video
        :param script_context: Script text for mood analysis
        :param volume: Override BGM volume (0.0-1.0). None uses config default.
        :param has_speech: If True, enables dynamic volume ducking during speech.
        :return: Path to output video with BGM mixed in
        """
        try:
            mood = await self.analyze_script(script_context)
            logger.info(f"[BGM] Script mood: {mood.upper()}")

            bgm_filename = self.MOOD_INVENTORY.get(mood, "happy_tune.mp3")
            bgm_file = self.music_dir / bgm_filename

            if not bgm_file.exists():
                logger.warning(f"[BGM] File {bgm_file} not found. Skipping BGM.")
                return video_path

            effective_volume = volume if volume is not None else self.default_volume
            output_path = str(video_path).replace(".mp4", f"_{mood}_bgm.mp4")

            await self._run_ffmpeg_mix(video_path, str(bgm_file), output_path,
                                       effective_volume, has_speech)
            logger.info(f"[BGM] Applied {mood} BGM at vol={effective_volume}. Output: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"[BGM] Error: {e}. Returning original video.")
            return video_path
