import sys
import os
import argparse
import asyncio
from pathlib import Path

# Add src/ to sys path to resolve 'commercial_engine'
sys.path.append(str(Path(__file__).parent.parent))

from workflows.ecommerce_pipeline import EcommercePipeline
from workflows.microdrama_pipeline import MicrodramaPipeline
from workflows.engineering_pipeline import EngineeringPipeline

async def main():
    parser = argparse.ArgumentParser(description="Agency-Agents Commercial Orchestrator")
    parser.add_argument("pipeline", choices=["ecommerce", "microdrama", "engineering"], help="Which pipeline to run")
    parser.add_argument("--topic", type=str, required=True, help="The product name, drama theme, or engineering feature request")
    parser.add_argument("--features", type=str, default="", help="Product features (E-commerce only)")
    
    args = parser.parse_args()
    repo_root = str(Path(__file__).parent.parent.parent)
    
    if args.pipeline == "ecommerce":
        pipeline = EcommercePipeline(repo_root)
        await pipeline.run(args.topic, args.features)
    elif args.pipeline == "microdrama":
        pipeline = MicrodramaPipeline(repo_root)
        await pipeline.run(args.topic)
    elif args.pipeline == "engineering":
        pipeline = EngineeringPipeline(repo_root)
        await pipeline.run(args.topic)

if __name__ == "__main__":
    asyncio.run(main())
