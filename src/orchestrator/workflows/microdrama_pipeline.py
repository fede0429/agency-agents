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
        try:
            from commercial_engine.projects.animation.models import EpisodePlan, ScenePlan
            
            print("\n[Engine Handoff] Parsing JSON outline into EpisodePlan models...")
            
            # The LLM outputs a raw structure, let's normalize it to our EpisodePlan
            outline_data = json.loads(outline_json)
            episodes_list = outline_data if isinstance(outline_data, list) else outline_data.get("episodes", [])
            
            parsed_episodes: list[EpisodePlan] = []
            
            for index, ep in enumerate(episodes_list):
                scenes = []
                for sc in ep.get("scenes", []):
                    scenes.append(ScenePlan(
                        scene_id=sc.get("scene_id", f"e{index}_s{len(scenes)}"),
                        title=sc.get("title", ""),
                        location=sc.get("location", ""),
                        dramatic_purpose=sc.get("dramatic_purpose", ""),
                    ))
                    
                episode_plan = EpisodePlan(
                    episode_title=ep.get("episode_title", f"Episode {index+1}"),
                    synopsis=ep.get("synopsis", ""),
                    hook=ep.get("hook", ""),
                    cliffhanger=ep.get("cliffhanger", ""),
                    scenes=scenes
                )
                parsed_episodes.append(episode_plan)
                
            print(f"-> Successfully parsed {len(parsed_episodes)} EpisodePlan objects!")
            
            # Here we would dispatch to the Animation Orchestrator
            # e.g. orchestrator.process_episodes(parsed_episodes)
            # For this pipeline, we save out the parsed plans to demonstrate real object integration
            out_file = self.repo_root / "src" / "orchestrator" / "output" / f"microdrama_{theme[:10].replace(' ','_')}.json"
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump([ep.to_dict() for ep in parsed_episodes], f, ensure_ascii=False, indent=2)
                
            print(f"-> Draft episodes dispatched to engine payload: {out_file}")
            
        except ImportError as e:
            print(f"[Warning] commercial_engine not fully configured/available yet: {e}")
        except json.JSONDecodeError:
            print("[Error] LLM did not return valid JSON for the Micro-Drama outline.")
        except Exception as e:
            print(f"[Error] Pipeline execution failed: {e}")
            
        return outline_json

if __name__ == "__main__":
    p = MicrodramaPipeline(str(Path(__file__).parent.parent.parent.parent))
    asyncio.run(p.run("A betrayed apprentice returns as a billionaire CEO"))
