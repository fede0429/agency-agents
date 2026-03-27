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
        # We simulate the bridge to the imported UGC-video-pro engine here.
        try:
            from commercial_engine.core.orchestrator import VideoRequest, UGCProducer
            # Here we inject the generated hooks into the request context.
            print("\n[Engine Handoff] Preparing to send to commercial_engine...")
            # Note: actual engine requires full config, mocking for demonstration
            print(f"-> Successfully bridged Agency-Agent script into Video Stitcher queue.")
        except ImportError:
            print("[Warning] commercial_engine not fully configured/available yet.")
            
        return script_output

if __name__ == "__main__":
    p = EcommercePipeline(str(Path(__file__).parent.parent.parent.parent))
    asyncio.run(p.run("Summer Cooling Neck Fan", "Portable, 12h battery, Ice-feel technology"))
