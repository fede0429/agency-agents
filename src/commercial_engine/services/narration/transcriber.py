import os
import json
import asyncio
from typing import List, Dict, Any
from openai import AsyncOpenAI
from utils.logger import get_logger
from utils.ffmpeg_tools import FFmpegTools

logger = get_logger(__name__)

class NarrationTranscriber:
    """ASR wrapper using OpenAI Whisper to generate timestamped subtitles."""
    
    def __init__(self, api_key: str = None):
        self.client = AsyncOpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.ffmpeg = FFmpegTools()

    async def transcribe_audio(self, audio_path: str) -> List[Dict[str, Any]]:
        """
        Transcribe audio and return segments with timestamps.
        Expected format:
        [
            {"text": "Hello world", "start": 0.0, "end": 2.5},
            {"text": "Welcome to the video", "start": 3.0, "end": 4.5}
        ]
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        logger.info(f"Transcribing audio: {audio_path} (Size: {file_size_mb:.2f} MB)")
        
        # Whisper limit is 25MB. We chunk if > 20MB for safety against ultra-long videos.
        if file_size_mb > 20.0:
            logger.info("Audio size > 20MB. Initiating anti-crash chunking protocol...")
            chunk_dir = os.path.join(os.path.dirname(audio_path), "transcribe_chunks")
            chunks = await self.ffmpeg.split_audio_by_time(audio_path, chunk_dir, segment_time=900)  # 15 min chunks
            
            formatted_segments = []
            current_offset = 0.0
            
            for chunk_path in chunks:
                logger.info(f"Transcribing chunk: {chunk_path} with temporal offset: {current_offset:.2f}s")
                with open(chunk_path, "rb") as audio_file:
                    response = await self.client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="verbose_json",
                        timestamp_granularities=["segment"]
                    )
                
                # Apply offset to this chunk
                for seg in response.segments:
                    # Depending on OpenAI SDK version, segments might be dicts or pydantic models
                    seg_text = seg.text if hasattr(seg, "text") else seg["text"]
                    seg_start = seg.start if hasattr(seg, "start") else seg["start"]
                    seg_end = seg.end if hasattr(seg, "end") else seg["end"]

                    formatted_segments.append({
                        "text": seg_text,
                        "start": seg_start + current_offset,
                        "end": seg_end + current_offset
                    })
                
                # Accurately probe duration to advance the offset lock
                chunk_duration = await self.ffmpeg.probe_duration(chunk_path)
                current_offset += chunk_duration
                
            logger.info(f"Batch chunk transcription complete: {len(formatted_segments)} segments across {len(chunks)} chunks.")
            return formatted_segments
        else:
            # Standard single-pass execution
            with open(audio_path, "rb") as audio_file:
                response = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )
            
            # Build segment payload
            segments = response.segments
            formatted_segments = []
            for seg in segments:
                seg_text = seg.text if hasattr(seg, "text") else seg["text"]
                seg_start = seg.start if hasattr(seg, "start") else seg["start"]
                seg_end = seg.end if hasattr(seg, "end") else seg["end"]

                formatted_segments.append({
                    "text": seg_text,
                    "start": seg_start,
                    "end": seg_end
                })
                
            logger.info(f"Transcription complete: {len(formatted_segments)} segments found.")
            return formatted_segments
