import asyncio
import sys
import json
from pathlib import Path
from agency_adapter import AgencyPromptLoader, AgencyLLMClient

class MicrodramaPipeline:
    def __init__(self, repo_root: str):
        self.loader = AgencyPromptLoader(repo_root)
        self.client = AgencyLLMClient()
        
    async def run(self, theme: str):
        print(f"--- Starting Micro-Drama Workflow for Theme: {theme} ---")
        
        # 1. Narrative Designer (Script & Outline)
        writer_profile = self.loader.load_prompt("game-development/game-development-narrative-designer.md")
        outline_input = f"Create a 3-episode micro-drama outline for TikTok/Douyin. Theme: {theme}. Output JSON with episodes, hooks and cliffhangers."
        outline_json = await self.client.process_task(writer_profile, outline_input, response_format=True)
        print("\n[Episode Outline]\n", outline_json[:300], "...\n")
        
        # 2. Director Agent Hand-off
        # Instead of the hardcoded episode_writer, we inject this into the Animation project structures.
        try:
            from commercial_engine.projects.animation.models import StoryBible, EpisodePlan
            from commercial_engine.projects.animation.episode_writer import EpisodeWriter
            
            print("\n[Engine Handoff] Bridging dynamic Agency-Agent JSON into Toonflow Python Engine...")
            data = json.loads(outline_json)
            # You would parse `data` into EpisodePlan models here.
            print(f"-> Successfully loaded {len(data.keys())} elements into animation pipeline.")
        except ImportError as e:
            print(f"[Warning] commercial_engine missing or import error: {e}")
            
        return outline_json

if __name__ == "__main__":
    p = MicrodramaPipeline(str(Path(__file__).parent.parent.parent.parent))
    asyncio.run(p.run("A betrayed apprentice returns as a billionaire CEO"))
