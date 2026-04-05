import os
from pathlib import Path
from typing import List, Dict, Any
from openai import AsyncOpenAI
from utils.logger import get_logger

logger = get_logger(__name__)

class NarrationTTS:
    """TTS wrapper utilizing OpenAI's audio speech API for streaming voiceovers."""
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini-tts", voice: str = "coral"):
        self.client = AsyncOpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model
        self.voice = voice
        
    async def synthesize_segments(self, script_segments: List[Dict[str, Any]], output_dir: str) -> List[Dict[str, Any]]:
        """
        Takes LLM generated rewritten scripts with timestamps and outputs them to audio files.
        Returns the segments enriched with audio file paths.
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        enriched_segments = []
        
        logger.info(f"Starting TTS generation for {len(script_segments)} segments using {self.model}.")
        
        for i, seg in enumerate(script_segments):
            text = seg.get("text", "")
            if not text:
                continue
                
            out_file = os.path.join(output_dir, f"narration_{i:03d}.wav")
            
            try:
                # Streaming to file for low latency processing per OpenAI's capability
                async with self.client.audio.speech.with_streaming_response.create(
                    model=self.model,
                    voice=self.voice,
                    input=text,
                    response_format="wav",
                ) as response:
                    await response.stream_to_file(out_file)
                
                enriched_segments.append({
                    "start": seg.get("start", 0),
                    "end": seg.get("end", 0),
                    "text": text,
                    "audio_path": out_file
                })
                logger.debug(f"Segment {i} saved to {out_file}")
            except Exception as e:
                logger.error(f"Failed to generate TTS for segment {i}: {e}")
                
        return enriched_segments
