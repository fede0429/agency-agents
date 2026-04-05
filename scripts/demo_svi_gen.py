import asyncio
import os
import sys

# Standardize python path for easy local execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from commercial_engine.services.video_gen.svi_pipeline import SVIPipeline

async def main():
    print("🚀 Starting SVI Demo via RunPod Serverless API...")
    
    # Check key (Assuming dotenv is loaded or key inserted correctly by the user/shell)
    # The script acts as a sandbox dry-run
    
    # Mocking out the TTS output
    segments = [
        {
            "start": 0.0, 
            "end": 4.5, 
            "text": "A cyber-aesthetic city skyline glowing with neon lights under rain. High quality, 4k.", 
            "audio_path": "dummy_audio_1.wav"
        }
    ]
    
    print(f"📦 Input Narration Segments:\n {segments}")
    
    pipeline = SVIPipeline()
    
    try:
        print("⏳ Waiting for SVI generation... this could take a few seconds/minutes...")
        enriched = await pipeline.generate_narration_video(segments)
        print("\n✅ Pipeline Completed!")
        for seg in enriched:
            print(f"--------------------------------------------------")
            print(f"- Narration: {seg.get('text')}")
            print(f"- Output Video URL: {seg.get('video_url', 'Failed to generate')}")
            print(f"--------------------------------------------------")
            
    except Exception as e:
        print(f"❌ Error during demo execution: {e}")

if __name__ == "__main__":
    asyncio.run(main())
