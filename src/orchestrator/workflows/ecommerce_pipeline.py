import asyncio
import sys
import json
from pathlib import Path
from agency_adapter import AgencyPromptLoader, AgencyLLMClient

class EcommercePipeline:
    def __init__(self, repo_root: str):
        self.loader = AgencyPromptLoader(repo_root)
        self.client = AgencyLLMClient()
        
    async def run(self, product_name: str, product_features: str):
        print(f"--- Starting E-commerce Workflow for {product_name} ---")
        
        # 1. Marketing / E-commerce Coach (Discover & Strategy)
        coach_profile = self.loader.load_prompt("marketing/marketing-china-ecommerce-operator.md")
        strategy_input = f"Analyze this product and create a sales strategy for TikTok/Douyin:\nProduct: {product_name}\nFeatures: {product_features}"
        strategy_output = await self.client.process_task(coach_profile, strategy_input)
        print("\n[Strategy Output]\n", strategy_output[:200], "...\n")
        
        # 2. Content Creator (Asset Generation)
        creator_profile = self.loader.load_prompt("marketing/marketing-content-creator.md")
        content_input = f"Based on this strategy, generate 3 highly converting hook lines and a 30s video script:\n{strategy_output}"
        script_output = await self.client.process_task(creator_profile, content_input)
        print("\n[Script Output]\n", script_output[:200], "...\n")
        
        # 3. Hand-off to Python Engine (Video Stitcher/Orchestrator)
        print("\n[Engine Handoff] Parsing script into structured VideoRequest...")
        parser_profile = self.loader.load_prompt("marketing/marketing-content-creator.md") # Repurpose to parse
        parse_input = (
            f"Extract the main visual prompt and metadata from this script.\n"
            f"Return ONLY valid JSON: {{\"text_prompt\": \"...\", \"duration\": 30, \"language\": \"zh\"}}\n"
            f"Script: {script_output}"
        )
        parsed_json = await self.client.process_task(parser_profile, parse_input, response_format=True)
        
        try:
            req_data = json.loads(parsed_json)
            import yaml
            
            # Load Commercial Engine config
            config_path = self.repo_root / "src" / "commercial_engine" / "config.yaml"
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                
            from commercial_engine.core.orchestrator import VideoRequest, VideoOrchestrator
            
            req = VideoRequest(
                user_id=1,
                chat_id=1,
                mode="text2video",
                model="auto",
                duration=req_data.get("duration", 30),
                language=req_data.get("language", "zh"),
                text_prompt=req_data.get("text_prompt", product_name),
            )
            
            orchestrator = VideoOrchestrator(config)
            print(f"-> Successfully parsed VideoRequest. Dispatching to VideoOrchestrator in background...")
            
            # Fire and forget in the background (or await if we want to block)
            # For pipeline demonstration, we will await it so the logs show.
            # In a real app, this would be: asyncio.create_task(orchestrator.generate(req))
            result = await orchestrator.generate(req)
            print(f"\n[Success] Video synthesized: {result.video_path}")
            
        except ImportError as e:
            print(f"[Warning] commercial_engine not fully configured/available yet: {e}")
        except Exception as e:
            print(f"[Error] Pipeline execution failed: {e}")
            
        return script_output

if __name__ == "__main__":
    import yaml # ensuring yaml is available
    p = EcommercePipeline(str(Path(__file__).parent.parent.parent.parent))
    asyncio.run(p.run("Summer Cooling Neck Fan", "Portable, 12h battery, Ice-feel technology"))
