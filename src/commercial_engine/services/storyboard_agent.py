"""
services/storyboard_agent.py
=============================
AI Storyboard Sub-Agent Pipeline — Structured short-drama generation.

Refactored to implement the "Toonflow" Segment/Shot split pattern for
reduced hallucination and strictly enforced JSON outputs.
Added DirectorAgent for orchestrating the sub-agents and yielding progress streams.
"""

import json
import logging
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Optional, AsyncGenerator, Dict, Any

logger = logging.getLogger(__name__)

# ─── Data Models ────────────────────────────────────────────────────────────

@dataclass
class Asset:
    type: str
    name: str
    description: str = ""

@dataclass
class Segment:
    index: int
    description: str
    emotion: str = ""
    action: str = ""
    duration_seconds: int = 5

@dataclass
class Shot:
    id: int
    segment_index: int
    prompt_zh: str
    prompt_en: str = ""
    camera_angle: str = ""
    duration_seconds: int = 3

@dataclass
class Episode:
    title: str
    episode_index: int = 1
    core_conflict: str = ""
    opening_hook: str = ""
    ending_hook: str = ""
    emotional_curve: str = ""
    key_events: list[str] = field(default_factory=list)
    visual_highlights: list[str] = field(default_factory=list)
    classic_quotes: list[str] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    shots: list[Shot] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

# ─── Base Sub-Agent ─────────────────────────────────────────────────────────

class BaseSubAgent:
    def __init__(self, config: dict):
        self.config = config
        self._api_key = config.get("openai", {}).get("api_key", "mock-key")
        self._base_url = config.get("openai", {}).get("base_url", "https://api.openai.com/v1")
        self._model = config.get("storyboard", {}).get("model", "gpt-4o-mini")

    async def _llm_json(self, system_prompt: str, user_prompt: str) -> dict:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
            resp = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
            )
            import re
            raw = resp.choices[0].message.content.strip()
            cleaned = re.sub(r'^```(?:json)?\s*', '', raw)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] LLM call failed. {e}")
            return {}

# ─── Sub-Agents ─────────────────────────────────────────────────────────────

class AssetAgent(BaseSubAgent):
    """Extracts characters, props, and scenes."""
    async def extract(self, script_text: str) -> list[Asset]:
        system = "你是一个AI资产管理师，擅长从剧本中提取角色、道具和场景。输出严格JSON。"
        user = (
            f"从以下剧本提取出场角色、关键道具和场景。\n\n"
            f"剧本：\n{script_text[:2000]}\n\n"
            f'输出JSON格式：{{"assets": [{{"type": "character/prop/scene", "name": "名称", "description": "描述"}}]}}'
        )
        data = await self._llm_json(system, user)
        return [Asset(**a) for a in data.get("assets", [])]

class SegmentAgent(BaseSubAgent):
    """Breaks script into emotional segments (起承转合)."""
    async def generate(self, script_text: str, style: str = "") -> list[Segment]:
        system = "你是一个专业的短剧分镜编导，将剧本拆解为情感节奏分明的片段。输出严格JSON。"
        user = (
            f"将以下剧本拆分为4-8个片段，需带明确情绪标签。\n风格：{style}\n剧本：\n{script_text[:3000]}\n\n"
            f'输出JSON格式：{{"segments": [{{"index": 1, "description": "...", "emotion": "...", "action": "...", "duration_seconds": 5}}]}}'
        )
        data = await self._llm_json(system, user)
        return [Segment(**s) for s in data.get("segments", [])]

class ShotAgent(BaseSubAgent):
    """Generates shot-by-shot prompts for segments with asset references."""
    async def generate(self, segments: list[Segment], assets: list[Asset], style: str = "") -> list[Shot]:
        system = "你是一个专业AI分镜师，为片段生成精确镜头提示词（兼顾人物动作、场景）。输出严格JSON。"
        seg_str = json.dumps([asdict(s) for s in segments], ensure_ascii=False)
        ast_str = json.dumps([asdict(a) for a in assets], ensure_ascii=False)
        user = (
            f"为以下片段生成分镜（每片段1-3个镜头）。结合已知资产。\n"
            f"资产：{ast_str}\n片段：{seg_str}\n风格：{style}\n\n"
            f'输出JSON格式：{{"shots": [{{"id": 1, "segment_index": 1, "prompt_zh": "中文提示词", '
            f'"prompt_en": "英文提示词", "camera_angle": "特写/全景", "duration_seconds": 3}}]}}'
        )
        data = await self._llm_json(system, user)
        return [Shot(**s) for s in data.get("shots", [])]

# ─── Orchestrator (Director) ────────────────────────────────────────────────

class DirectorAgent:
    """
    Coordinates AssetAgent, SegmentAgent, and ShotAgent.
    Yields progress events (SSE compatible) during the generation lifecycle.
    """
    def __init__(self, config: dict):
        self.config = config
        self.asset_agent = AssetAgent(config)
        self.segment_agent = SegmentAgent(config)
        self.shot_agent = ShotAgent(config)

    async def generate_episode_stream(self, script_text: str, title: str = "Episode 1", style: str = "") -> AsyncGenerator[Dict[str, Any], None]:
        """Yields progress dicts incrementally."""
        
        yield {"step": "init", "status": "processing", "message": "Initializing Director..."}
        await asyncio.sleep(0.5)

        # 1. Assets
        yield {"step": "assets", "status": "processing", "message": "Extracting script assets (characters/scenes/props)..."}
        assets = await self.asset_agent.extract(script_text)
        yield {"step": "assets", "status": "success", "data": len(assets)}

        # 2. Segments
        yield {"step": "segments", "status": "processing", "message": "Segmenting script into emotional arcs..."}
        segments = await self.segment_agent.generate(script_text, style)
        yield {"step": "segments", "status": "success", "data": len(segments)}

        # 3. Shots
        yield {"step": "shots", "status": "processing", "message": f"Drafting detailed shots for {len(segments)} segments..."}
        shots = await self.shot_agent.generate(segments, assets, style)
        yield {"step": "shots", "status": "success", "data": len(shots)}

        # 4. Packaging
        yield {"step": "packaging", "status": "processing", "message": "Finalizing episode structure..."}
        episode = Episode(
            title=title,
            assets=assets,
            segments=segments,
            shots=shots,
        )
        
        yield {"step": "complete", "status": "success", "episode": episode.to_dict()}
