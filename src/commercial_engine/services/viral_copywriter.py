"""
services/viral_copywriter.py
============================
Auto-generates viral titles, descriptions, and hashtags for social media
using the LLM API, with support for:
  - Multi-language output (zh, en, ja, ko, etc.)
  - Platform-specific optimization (TikTok, YouTube, Douyin, Instagram)
  - Emotional hook analysis
  - Trending hashtag injection
"""
import json
import re
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class ViralCopywriter:
    def __init__(self, config: dict):
        self.config = config

        # API credentials
        api_key = config.get("kie", {}).get("api_key") or config.get("openai", {}).get("api_key")
        base_url = config.get("kie", {}).get("base_url") or config.get("openai", {}).get("base_url", "https://api.openai.com/v1")
        self.model = config.get("viral_copywriter", {}).get("model", "gpt-4o-mini")

        if not api_key:
            logger.warning("ViralCopywriter: No API key — generations will use fallback")

        self.client = AsyncOpenAI(api_key=api_key or "missing", base_url=base_url)

    async def generate_content(self, video_context: str, language: str = "auto",
                               platforms: list[str] | None = None) -> dict:
        """
        Generate viral title, description, and tags.

        :param video_context: Script text or video description (max ~1500 chars recommended)
        :param language: Target language (zh, en, ja, auto). 'auto' lets LLM detect.
        :param platforms: Target platforms (tiktok, douyin, youtube, instagram). Default: all.
        :return: dict with title, description, tags, and per-platform hooks.
        """
        # Truncate context to prevent token waste
        context = video_context[:1500] if video_context else "AI Generated Video"

        platform_list = platforms or ["tiktok", "douyin", "youtube", "instagram"]
        platform_str = ", ".join(platform_list)

        lang_instruction = ""
        if language == "zh":
            lang_instruction = "所有文案必须使用中文。标题要带网感，使用爆款句式（如省略号悬疑式、反问式、感叹式）。"
        elif language == "en":
            lang_instruction = "All copy MUST be in English. Use viral hooks (curiosity gaps, power words, emotional triggers)."
        elif language == "ja":
            lang_instruction = "すべてのコピーは日本語でなければなりません。"
        else:
            lang_instruction = "Auto-detect the most suitable language based on the content. Use that language for all outputs."

        prompt = (
            f"You are a top-tier viral social media copywriter specializing in short-form video.\n\n"
            f"TARGET PLATFORMS: {platform_str}\n"
            f"{lang_instruction}\n\n"
            f"VIDEO CONTEXT:\n{context}\n\n"
            f"Generate the following:\n"
            f"1. 'title': An extremely catchy, scroll-stopping title (max 50 chars). "
            f"Use emotional hooks: curiosity gaps, power words, controversy, or numbers.\n"
            f"2. 'description': An engaging description that drives comments and shares (max 200 chars). "
            f"Include a call-to-action.\n"
            f"3. 'tags': Array of 5-8 trending and relevant hashtags (strings, WITHOUT # prefix).\n"
            f"4. 'platform_hooks': Object with per-platform optimized one-liner hooks:\n"
            f"   - 'tiktok': TikTok-style hook (edgy, Gen-Z tone)\n"
            f"   - 'douyin': 抖音风格 hook (网感、争议性)\n"
            f"   - 'youtube': YouTube SEO-optimized title\n"
            f"   - 'instagram': Instagram Reels caption\n\n"
            f"You MUST return valid JSON ONLY."
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a JSON-only viral marketing AI. Output ONLY valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.85,
            )

            raw = response.choices[0].message.content.strip()
            # Strip markdown fences if present
            cleaned = re.sub(r'^```(?:json)?\s*', '', raw)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            viral_data = json.loads(cleaned)

            # Type safety
            tags = viral_data.get("tags", [])
            if not isinstance(tags, list):
                tags = [t.strip() for t in str(tags).split(",")]
            # Strip # prefix from tags
            tags = [t.lstrip("#").strip() for t in tags if t.strip()]

            platform_hooks = viral_data.get("platform_hooks", {})
            if not isinstance(platform_hooks, dict):
                platform_hooks = {}

            result = {
                "title": str(viral_data.get("title", ""))[:80],
                "description": str(viral_data.get("description", ""))[:500],
                "tags": tags[:10],
                "platform_hooks": platform_hooks,
            }
            logger.info(f"[ViralCopy] Title: {result['title']} | Tags: {len(result['tags'])}")
            return result

        except Exception as e:
            logger.error(f"ViralCopywriter generation failed: {e}")
            return self._fallback(language)

    @staticmethod
    def _fallback(language: str = "auto") -> dict:
        """Safe fallback when LLM call fails."""
        if language == "zh":
            return {
                "title": "AI生成的惊艳视频",
                "description": "这个视频太绝了！点赞关注不迷路～",
                "tags": ["AI", "短视频", "热门"],
                "platform_hooks": {},
            }
        return {
            "title": "AI Generated Viral Video",
            "description": "Check out this amazing AI video! Like & Follow for more 🔥",
            "tags": ["AI", "Video", "Trending", "Viral"],
            "platform_hooks": {},
        }
