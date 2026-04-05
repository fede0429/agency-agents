import os
import time
from typing import Dict, Any

from utils.logger import get_logger
from utils.ffmpeg_tools import FFmpegTools
from services.narration.transcriber import NarrationTranscriber
from services.narration.script_writer import NarrationScriptWriter
from services.narration.tts import NarrationTTS

logger = get_logger(__name__)

class NarrationPipeline:
    """Orchestrates the Audio Extraction -> ASR -> LLM -> TTS -> Audio Ducking Mixing flow."""
    
    def __init__(self, output_dir: str = "/tmp/narration_pipeline"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.transcriber = NarrationTranscriber()
        self.script_writer = NarrationScriptWriter()
        self.tts = NarrationTTS()
        self.ffmpeg = FFmpegTools()

    async def run_pipeline(self, video_path: str, style: str = "纪录片解说") -> Dict[str, Any]:
        """
        Executes the AI Voiceover generation pipeline.
        Returns the path to the final video with ducked narration.
        """
        logger.info(f"Starting AI Narration Pipeline for {video_path}")
        task_id = f"job_{int(time.time()*1000)}"
        job_dir = os.path.join(self.output_dir, task_id)
        os.makedirs(job_dir, exist_ok=True)
        
        # 1. Extract Background Audio
        bgm_audio_path = os.path.join(job_dir, "original_bgm.mp3")
        await self.ffmpeg.extract_audio(input_video=video_path, output_path=bgm_audio_path)
        
        # 2. Transcribe Audio bounds/frames via Whisper
        transcript_segments = await self.transcriber.transcribe_audio(bgm_audio_path)
        
        # 3. Rewrite Script strictly bounded by WPM constraints
        script_segments = await self.script_writer.rewrite_narrative(
            transcript_segments=transcript_segments, 
            style=style
        )
        
        # 4. Synthesize TTS
        tts_dir = os.path.join(job_dir, "tts")
        enriched_segments = await self.tts.synthesize_segments(
            script_segments=script_segments, 
            output_dir=tts_dir
        )
        
        # 5. Concatenate TTS segments (if needed) and run ducking mix
        # Usually, TTS chunks should be placed accurately on a timeline rather than concatenated blind.
        # But for MVP, if we concatenate padded audio or run complex mixing:
        
        # We will create an empty audio canvas and inject TTS at proper timestamps
        # This requires complex ffmpeg adelay filters. 
        # For simplicity, we assume we concat the TTS voices to a single track with correct silences 
        # or we just duck the entire timeline sequentially.
        
        # Using concat for now as MVP. A true implementation would use a timeline file.
        audio_paths = [seg["audio_path"] for seg in enriched_segments if "audio_path" in seg]
        merged_voice_path = os.path.join(job_dir, "merged_narration.wav")
        
        if audio_paths:
            await self.ffmpeg.concat_audio_clips(audio_paths, merged_voice_path)
        else:
            # Fallback if TTS failed
            merged_voice_path = bgm_audio_path

        # 6. Audio Ducking Mix back onto original video
        final_video_path = os.path.join(job_dir, "final_narrated_video.mp4")
        if os.path.exists(merged_voice_path) and merged_voice_path != bgm_audio_path:
            await self.ffmpeg.ducking_mix_narration(
                input_video=video_path, 
                narration_audio=merged_voice_path, 
                output_path=final_video_path
            )
        else:
            # If no narration generated, just return original
            final_video_path = video_path
            
        logger.info(f"AI Narration Pipeline complete! Output: {final_video_path}")
        
        return {
            "task_id": task_id,
            "final_video": final_video_path,
            "segments": enriched_segments
        }
