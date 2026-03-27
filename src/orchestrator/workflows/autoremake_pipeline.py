"""
workflows/autoremake_pipeline.py
================================
Competitor Video Auto-Remake Pipeline (Deep Intelligence Edition).

Flow:
  1. Deep Extract: Download competitor video → extract audio → Whisper transcribe → harvest metadata
  2. Agent Rewrite: Marketing Coach rewrites the transcript into an original viral script
  3. Video Generate: Dispatch to VideoOrchestrator with rewritten script + original video as reference
  4. Auto-Publish: Generated video auto-syndicates to all configured platforms
"""

import asyncio
import sys
import re
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
        print(f"--- Starting Auto-Remake Pipeline (Deep Intelligence) for URL: {url} ---")
        
        try:
            from commercial_engine.services.video_intelligence import VideoIntelligenceExtractor
            from commercial_engine.core.orchestrator import VideoRequest, VideoOrchestrator
            
            # ═══════════════════════════════════════════════════════════════
            # Step 1: Deep Video Intelligence Extraction
            # ═══════════════════════════════════════════════════════════════
            print("\n[1/4] Deep extracting competitor video content...")
            extractor = VideoIntelligenceExtractor(self.config)
            report = await extractor.analyze(url)
            
            if not report.transcript and not report.original_title:
                print("[Error] Failed to extract any content from the URL.")
                print("  -> Ensure yt-dlp is installed: pip install yt-dlp")
                return None
            
            print(f"  ✓ Platform: {report.platform.upper()}")
            print(f"  ✓ Title: {report.original_title}")
            print(f"  ✓ Creator: {report.creator}")
            print(f"  ✓ Duration: {report.duration_seconds:.0f}s")
            print(f"  ✓ Views: {report.view_count:,}")
            print(f"  ✓ Transcript: {len(report.transcript)} chars ({report.transcript_language})")
            if report.original_tags:
                print(f"  ✓ Tags: {', '.join(report.original_tags[:5])}")
            
            # ═══════════════════════════════════════════════════════════════
            # Step 2: Construct Rich Context for Agent Rewrite
            # ═══════════════════════════════════════════════════════════════
            print("\n[2/4] Analyzing and rewriting with Marketing Agent...")
            
            # Build the full intelligence context
            intel_context = report.to_prompt_context()
            
            coach_profile = self.loader.load_prompt("marketing/marketing-short-video-editing-coach.md")
            rewrite_prompt = (
                f"你是一个顶级短视频编导和洗稿大师。以下是我们通过AI深度分析提取的一个竞品爆款视频的完整情报：\n\n"
                f"{intel_context}\n\n"
                f"=== 你的任务 ===\n"
                f"1. 深度分析这个视频为什么能火（标题套路、脚本节奏、情绪高潮点）\n"
                f"2. 基于其核心爆点和叙事结构，完全原创重写一个更强的视频脚本\n"
                f"3. 保留爆款基因但确保通过平台原创查重\n\n"
                f"你 MUST output raw valid JSON ONLY containing these keys:\n"
                f"- 'text_prompt': 完整的重写后视频脚本描述（用于文生视频）\n"
                f"- 'duration': 建议视频时长（整数秒）\n"
                f"- 'language': 脚本语言代码 (如 'zh' 或 'en')\n"
                f"- 'viral_analysis': 一句话总结这个爆款的核心流量密码"
            )
            
            rewrite_json_str = await self.client.process_task(coach_profile, rewrite_prompt, response_format=True)
            
            # Sanitize: strip markdown code fences
            cleaned = re.sub(r'^```(?:json)?\s*', '', rewrite_json_str.strip())
            cleaned = re.sub(r'\s*```$', '', cleaned)
            
            try:
                rewritten_data = json.loads(cleaned)
            except json.JSONDecodeError as e:
                print(f"[Error] LLM returned invalid JSON. Parse error: {e}")
                print(f"[Debug] Raw output (first 500 chars): {rewrite_json_str[:500]}")
                return None
            
            print(f"  ✓ Rewrite complete!")
            if rewritten_data.get("viral_analysis"):
                print(f"  ✓ Viral DNA: {rewritten_data['viral_analysis']}")
            
            # ═══════════════════════════════════════════════════════════════
            # Step 3: Dispatch to VideoOrchestrator
            # ═══════════════════════════════════════════════════════════════
            print("\n[3/4] Dispatching to Commercial Engine VideoOrchestrator...")
            
            # Inject the original video's deep intelligence as url_content
            # so the script generator has maximum context
            enriched_context = (
                f"=== Original Competitor Intelligence ===\n{intel_context}\n\n"
                f"=== Agent Rewritten Script ===\n{rewritten_data.get('text_prompt', '')}"
            )
            
            req = VideoRequest(
                user_id=1,
                chat_id=1,
                mode="text2video",
                model="auto",
                duration=rewritten_data.get("duration", 30),
                language=rewritten_data.get("language", "zh"),
                text_prompt=rewritten_data.get("text_prompt", "AI Rewrite"),
                url=url,
                url_content=enriched_context,  # Pre-fill to skip re-extraction
            )
            
            orchestrator = VideoOrchestrator(self.config)
            result = await orchestrator.generate(req)
            
            # ═══════════════════════════════════════════════════════════════
            # Step 4: Summary
            # ═══════════════════════════════════════════════════════════════
            print(f"\n[4/4] ✅ Auto-Remake Complete!")
            print(f"  Original: {report.original_title} ({report.platform})")
            print(f"  Remade Video: {result.video_path}")
            if result.drive_link:
                print(f"  Cloud Backup: {result.drive_link}")
                
            # Cleanup downloaded video
            extractor.cleanup()
                
            return result
            
        except ImportError as e:
            print(f"[Warning] commercial_engine missing or import error: {e}")
        except Exception as e:
            print(f"[Error] Auto-Remake Pipeline execution failed: {e}")
            import traceback
            traceback.print_exc()
            
        return None


if __name__ == "__main__":
    p = AutoremakePipeline(str(Path(__file__).parent.parent.parent.parent))
    asyncio.run(p.run("https://v.douyin.com/ExampleURL/"))
