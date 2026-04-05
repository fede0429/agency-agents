import os
import json
from typing import List, Dict, Any
from openai import AsyncOpenAI
from utils.logger import get_logger

logger = get_logger(__name__)

class NarrationScriptWriter:
    """
    LLM wrapper for generating narration scripts strictly bounded by duration.
    Calculates constraints using WPM mapping to ensure TTS output fits the video segments.
    """
    
    WPM = 250  # Words (or Chinese chars) per minute TTS speed
    
    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        self.client = AsyncOpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model

    async def rewrite_narrative(
        self, 
        transcript_segments: List[Dict[str, Any]], 
        style: str = "纪录片解说"
    ) -> List[Dict[str, Any]]:
        """
        Takes raw ASR transcripts and outputs a polished narration script tailored to exact times.
        Ensures the text is not too long for the given duration window.
        """
        logger.info(f"Rewriting {len(transcript_segments)} segments into {style} style.")
        
        # Build prompt map summarizing the timing rules
        segment_lines = []
        for i, seg in enumerate(transcript_segments):
            dur = max(0.5, seg['end'] - seg['start'])
            max_chars = int((dur / 60.0) * self.WPM)
            segment_lines.append(
                f"[{seg['start']:.1f}s - {seg['end']:.1f}s] MAX_CHARS: {max_chars} | RAW_TEXT: {seg['text']}"
            )
            
        prompt = f"""
You are an expert Voiceover Scriptwriter. 
Rewrite the following raw video transcripts into a fluent spoken narration script.
Style: {style}

CRITICAL RULES:
1. You MUST respect the MAX_CHARS limit for each segment. Human TTS speaks at ~{self.WPM} chars/min. Overlong text will break the video sync.
2. The language MUST be Natural, Conversational Audio-focused Chinese. Avoid highly formal or dense text.
3. Return STRICTLY a JSON array of objects. 

Format:
[
  {{ "start": 0.0, "end": 2.5, "text": "你的精美解说词" }}
]

Raw Transcript & Bounds:
{chr(10).join(segment_lines)}
"""
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}, 
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        try:
            # Check if json wrapper e.g. {"script": [...]} was provided
            data = json.loads(content)
            if isinstance(data, dict):
                # Search for arrays in keys
                script_outputs = data.get("script", [])
                if not script_outputs:
                    for val in data.values():
                        if isinstance(val, list):
                            script_outputs = val
                            break
            else:
                script_outputs = data
                
            return script_outputs
            
        except Exception as e:
            logger.error(f"Failed to parse LLM JSON response: {e}\nContent: {content}")
            return transcript_segments # Fallback to original
