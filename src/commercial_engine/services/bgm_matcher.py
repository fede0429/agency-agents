import os
import json
import asyncio
import logging
from pathlib import Path
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class AIBGMMatcher:
    def __init__(self, config: dict):
        self.config = config
        
        # Load API keys
        api_key = config.get("kie", {}).get("api_key") or config.get("openai", {}).get("api_key")
        base_url = config.get("kie", {}).get("base_url") or config.get("openai", {}).get("base_url", "https://api.openai.com/v1")
        self.model = config.get("bgm_matcher", {}).get("model", "gpt-4o")
        
        self.llm_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        
        # Local BGM Inventory (Mock Directory mapping)
        self.music_dir = Path(config.get("bgm_dir", "assets/music"))
        self.music_inventory = {
            "happy": "happy_tune.mp3",
            "sad": "sad_melody.mp3",
            "exciting": "epic_beat.mp3",
            "relaxed": "chill_lofi.mp3",
            "mysterious": "dark_synth.mp3"
        }

    async def analyze_script(self, script_context: str) -> str:
        """Analyzes the script to extract the dominant emotional mood."""
        prompt = (
            f"Analyze the following video script and determine its core emotional mood. "
            f"You must categorize it exactly into one of the following 5 moods: "
            f"[happy, sad, exciting, relaxed, mysterious].\n\n"
            f"SCRIPT:\n{script_context}\n\n"
            f"Return ONLY valid JSON with exactly one key: 'mood'."
        )
        
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a musical emotion analyzer returning JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            data = json.loads(response.choices[0].message.content)
            mood = data.get("mood", "happy").lower().strip()
            
            if mood not in self.music_inventory:
                mood = "happy"
                
            return mood
        except Exception as e:
            logger.warning(f"BGM Matcher LLM analysis failed: {e}. Defaulting to 'happy'.")
            return "happy"

    async def _run_ffmpeg_async(self, video_path: str, bgm_file: str, output_path: str):
        """Runs ffmpeg asynchronously using subprocess.exec to prevent blocking."""
        logger.info(f"Mixing Video: {video_path} with BGM ({bgm_file})")
        
        # ffmpeg -i video.mp4 -i bgm.mp3 -filter_complex "[1:a]volume=0.15[a1];[0:a][a1]amix=inputs=2:duration=first" -c:v copy -y output.mp4
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(bgm_file),
            "-filter_complex", "[1:a]volume=0.15[a1];[0:a][a1]amix=inputs=2:duration=first",
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
            error_details = stderr.decode('utf-8', errors='ignore')
            raise RuntimeError(f"FFmpeg mixing failed: {error_details}")

    async def add_bgm(self, video_path: str, script_context: str) -> str:
        """Main entry point to analyze mood, pick music, and mix it."""
        try:
            mood = await self.analyze_script(script_context)
            logger.info(f"[BGM Matcher] Script Mood analyzed as: {mood.upper()}")
            
            bgm_filename = self.music_inventory.get(mood, "happy_tune.mp3")
            bgm_file = self.music_dir / bgm_filename
            
            # If the file doesn't exist, we skip mixing instead of crashing
            if not bgm_file.exists():
                logger.warning(f"BGM file {bgm_file} not found locally! Skipping BGM addition.")
                return video_path
                
            output_video_path = str(video_path).replace(".mp4", f"_{mood}_bgm.mp4")
            
            await self._run_ffmpeg_async(video_path, str(bgm_file), output_video_path)
            logger.info(f"[BGM Matcher] Successfully applied BGM. Final path: {output_video_path}")
            
            return output_video_path
            
        except Exception as e:
            logger.error(f"Error adding BGM: {e}. Falling back to original video.")
            return video_path
