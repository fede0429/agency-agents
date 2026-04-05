import os
import asyncio
from typing import List, Dict, Any

from utils.logger import get_logger
from .api_client import RunPodAPIClient

logger = get_logger(__name__)

class SVIPipeline:
    """
    Adapter bridging AI Narration Pipeline segments and RunPod Serverless SVI deployments.
    """
    
    def __init__(self, runpod_client: RunPodAPIClient = None):
        self.client = runpod_client or RunPodAPIClient()
        self.chunk_duration = 5.0

    async def generate_narration_video(self, segments: List[Dict[str, Any]], base_image_url: str = None) -> List[Dict[str, Any]]:
        logger.info(f"Starting RunPod SVI integration pipeline for {len(segments)} segments.")
        enriched_segments = []
        
        for i, segment in enumerate(segments):
            text = segment.get("text", "")
            if not text:
                continue
                
            logger.debug(f"Tasking RunPod with segment {i+1}/{len(segments)}: {text[:30]}...")
            
            prompt = f"Cinematic video snippet portraying: {text}"
            
            try:
                # Issue generating one clip via RunPod Serverless API
                video_url = await self.client.generate_video(prompt=prompt, image_url=base_image_url)
                
                current_segment = segment.copy()
                current_segment["video_url"] = video_url
                enriched_segments.append(current_segment)
                
            except Exception as e:
                logger.error(f"Failed to generate video layer for segment {i}: {e}")
                enriched_segments.append(segment)
                
        logger.info(f"SVI Pipeline completed via RunPod. Generated {len([s for s in enriched_segments if 'video_url' in s])} video clips.")
        return enriched_segments
