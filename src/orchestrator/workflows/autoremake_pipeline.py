import asyncio
import sys
import json
import yaml
from pathlib import Path

from agency_adapter import AgencyPromptLoader, AgencyLLMClient

class AutoremakePipeline:
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self.loader = AgencyPromptLoader(repo_root)
        self.client = AgencyLLMClient()
        
        # Load Commercial Engine config
        config_path = self.repo_root / "src" / "commercial_engine" / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    async def run(self, url: str):
        print(f"--- Starting Auto-Remake Pipeline for URL: {url} ---")
        
        try:
            from commercial_engine.services.url_extractor import URLExtractor
            from commercial_engine.core.orchestrator import VideoRequest, VideoOrchestrator
            
            # Step 1: Extract competitor script
            print("\n[1/3] Extracting competitor content...")
            extractor = URLExtractor(self.config)
            extracted_script = await extractor.extract(url)
            
            if not extracted_script:
                print("[Error] Failed to extract any valid content from the URL.")
                return None
                
            print(f"-> Extraction success ({len(extracted_script)} chars)")
            
            # Step 2: Rewrite using Agency-Agent (Marketing Coach)
            print("\n[2/3] Analyzing and rewriting script with Marketing Agent...")
            coach_profile = self.loader.load_prompt("marketing/marketing-short-video-editing-coach.md")
            rewrite_prompt = (
                f"You are a master viral video scriptwriter. Take the following competitor script and deeply remold it. "
                f"Make it structurally superior, more engaging, highly viral, and completely original to avoid plagiarism.\n\n"
                f"COMPETITOR SCRIPT:\n{extracted_script}\n\n"
                f"You MUST output raw valid JSON ONLY containing these keys: \n"
                f"- 'text_prompt': The full rewritten video script description.\n"
                f"- 'duration': Interstitial duration estimate (integer seconds, e.g. 30).\n"
                f"- 'language': The language code of the script (e.g. 'zh' or 'en')."
            )
            
            rewrite_json_str = await self.client.process_task(coach_profile, rewrite_prompt, response_format=True)
            
            # Sanitize: strip markdown code fences if LLM wraps JSON
            import re
            cleaned = re.sub(r'^```(?:json)?\s*', '', rewrite_json_str.strip())
            cleaned = re.sub(r'\s*```$', '', cleaned)
            
            try:
                rewritten_data = json.loads(cleaned)
            except json.JSONDecodeError as e:
                print(f"[Error] LLM returned invalid JSON. Parse error: {e}")
                print(f"[Debug] Raw LLM output (first 500 chars): {rewrite_json_str[:500]}")
                return None
            
            print("-> Rewrite success! Originality injected.")
            
            # Step 3: Dispatch to VideoOrchestrator
            print("\n[3/3] Dispatching to Commercial Engine Video Orchestrator...")
            req = VideoRequest(
                user_id=1,
                chat_id=1,
                mode="text2video",
                model="auto",
                duration=rewritten_data.get("duration", 30),
                language=rewritten_data.get("language", "zh"),
                text_prompt=rewritten_data.get("text_prompt", "AI Rewrite"),
                url=url, # Retain original URL for reference
            )
            
            orchestrator = VideoOrchestrator(self.config)
            result = await orchestrator.generate(req)
            
            print(f"\n[Success] Remade Video synthesized: {result.video_path}")
            if result.drive_link:
                print(f"-> Backed up at: {result.drive_link}")
                
            return result
            
        except ImportError as e:
            print(f"[Warning] commercial_engine missing or import error: {e}")
        except Exception as e:
            print(f"[Error] Auto-Remake Pipeline execution failed: {e}")
            
        return None

if __name__ == "__main__":
    p = AutoremakePipeline(str(Path(__file__).parent.parent.parent.parent))
    asyncio.run(p.run("https://v.douyin.com/ExampleURL/"))
