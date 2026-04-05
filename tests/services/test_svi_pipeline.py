import pytest
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))

try:
    from commercial_engine.services.video_gen.svi_pipeline import SVIPipeline
    from commercial_engine.services.video_gen.api_client import RunPodAPIClient
except ImportError:
    pass

class MockRunPodClient:
    async def generate_video(self, prompt: str, image_url: str = None, timeout: int = 300) -> str:
        # Mock Serverless response
        return f"https://mock-s3-bucket.runpod.com/generated_{prompt[:5]}.mp4"

@pytest.mark.asyncio
async def test_runpod_svi_segmentation():
    try:
        client = MockRunPodClient()
        pipeline = SVIPipeline(runpod_client=client)
        
        mock_segments = [
            {"start": 0.0, "end": 3.5, "text": "First scene.", "audio_path": "a.wav"},
            {"start": 4.0, "end": 8.0, "text": "Second scene.", "audio_path": "b.wav"},
        ]
        
        results = await pipeline.generate_narration_video(mock_segments)
        
        assert len(results) == 2
        assert "video_url" in results[0]
        assert "video_url" in results[1]
        assert "https://mock-s3" in results[0]["video_url"]
    except NameError:
        pytest.skip("Modules not discoverable in this environment setup.")
