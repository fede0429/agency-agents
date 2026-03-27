"""
services/storyboard_agent.py
=============================
AI Storyboard Agent — Structured short-drama generation pipeline.

Inspired by Toonflow's architecture, this implements a multi-agent storyboard
system that converts scripts into structured Episode → Segment → Shot pipelines:

  1. SegmentAgent: Breaks scripts into emotional segments (起承转合)
  2. ShotAgent: Generates shot-by-shot prompts for each segment
  3. Director: Orchestrates the full pipeline and manages assets

Uses LLM (AsyncOpenAI) for all generation steps with structured JSON output.
"""

import json
import logging
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Data Models ────────────────────────────────────────────────────────────

@dataclass
class Asset:
    """A named asset (character, prop, or scene)."""
    type: str       # "character", "prop", "scene"
    name: str
    description: str = ""

@dataclass
class Segment:
    """A logical segment of a story (起承转合)."""
    index: int
    description: str
    emotion: str = ""       # e.g. "紧张", "温馨", "高潮"
    action: str = ""        # primary action in this segment
    duration_seconds: int = 5

@dataclass
class Shot:
    """A single shot within a segment."""
    id: int
    segment_index: int
    prompt_zh: str           # Chinese prompt for image/video generation
    prompt_en: str = ""      # Optional English translation
    camera_angle: str = ""   # 特写/全景/中景/俯拍 etc.
    duration_seconds: int = 3

@dataclass
class Episode:
    """A complete episode structure for short-drama generation."""
    title: str
    episode_index: int = 1
    core_conflict: str = ""
    opening_hook: str = ""
    ending_hook: str = ""
    emotional_curve: str = ""                  # e.g. "平静→紧张→高潮→释然"
    key_events: list[str] = field(default_factory=list)  # [起, 承, 转, 合]
    visual_highlights: list[str] = field(default_factory=list)
    classic_quotes: list[str] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    shots: list[Shot] = field(default_factory=list)

    def to_script_prompt(self) -> str:
        """Format episode into a structured LLM prompt (Toonflow-style)."""
        sections = [
            f"═══════════════════════════════════════",
            f"第{self.episode_index}集：{self.title}",
            f"═══════════════════════════════════════",
        ]

        # Assets
        chars = [a for a in self.assets if a.type == "character"]
        props = [a for a in self.assets if a.type == "prop"]
        scenes = [a for a in self.assets if a.type == "scene"]

        if chars:
            sections.append("\n【出场角色】")
            for c in chars:
                sections.append(f"  角色：{c.name} — {c.description}")
        if scenes:
            sections.append("\n【场景列表】")
            for s in scenes:
                sections.append(f"  场景：{s.name} — {s.description}")
        if props:
            sections.append("\n【关键道具】")
            for p in props:
                sections.append(f"  道具：{p.name} — {p.description}")

        if self.core_conflict:
            sections.append(f"\n【核心矛盾】{self.core_conflict}")
        if self.opening_hook:
            sections.append(f"【开场镜头】{self.opening_hook}")
        if self.key_events:
            labels = ["起", "承", "转", "合"]
            sections.append("\n【剧情节点】")
            for i, ev in enumerate(self.key_events):
                label = labels[i] if i < len(labels) else str(i+1)
                sections.append(f"  【{label}】{ev}")
        if self.emotional_curve:
            sections.append(f"\n【情绪曲线】{self.emotional_curve}")
        if self.visual_highlights:
            sections.append("\n【视觉重点】")
            for i, h in enumerate(self.visual_highlights, 1):
                sections.append(f"  镜头{i}：{h}")
        if self.ending_hook:
            sections.append(f"\n【结尾悬念】{self.ending_hook}")
        if self.classic_quotes:
            sections.append("\n【黄金金句】")
            for q in self.classic_quotes:
                sections.append(f"  「{q}」")

        return "\n".join(sections)

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Storyboard Agent ──────────────────────────────────────────────────────

class StoryboardAgent:
    """
    AI-powered storyboard generator.

    Decomposes a script/story into structured Episodes with segments and shots,
    ready for video generation.

    Usage:
        agent = StoryboardAgent(config)
        episode = await agent.generate_episode(
            script_text="...",
            title="第1集：命运的转折",
            style="古风仙侠"
        )
        # episode.segments → emotional arcs
        # episode.shots → shot-by-shot prompts for video generation
    """

    def __init__(self, config: dict):
        self.config = config
        api_key = config.get("kie", {}).get("api_key") or config.get("openai", {}).get("api_key")
        base_url = config.get("kie", {}).get("base_url") or config.get("openai", {}).get("base_url", "https://api.openai.com/v1")
        self._api_key = api_key
        self._base_url = base_url

    async def _llm_json(self, system_prompt: str, user_prompt: str) -> dict:
        """Call LLM with JSON mode and return parsed dict."""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
            resp = await client.chat.completions.create(
                model=self.config.get("storyboard", {}).get("model", "gpt-4o-mini"),
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
            logger.error(f"[StoryboardAgent] LLM call failed: {e}")
            return {}

    # ─── Step 1: Segment Agent ──────────────────────────────────────────

    async def _generate_segments(self, script_text: str, style: str = "") -> list[Segment]:
        """Break script into emotional segments (起承转合)."""
        system = (
            "你是一个专业的短剧分镜编导，擅长将剧本拆解为情感节奏分明的片段。"
            "你的输出是严格的JSON。"
        )
        user = (
            f"请将以下剧本拆分为4-8个片段，每个片段要有明确的情绪标签和主要动作。\n"
            f"风格：{style or '默认'}\n\n"
            f"剧本内容：\n{script_text[:3000]}\n\n"
            f"输出JSON格式：\n"
            f'{{"segments": [{{"index": 1, "description": "...", "emotion": "紧张/温馨/高潮/...", '
            f'"action": "主角做了什么", "duration_seconds": 5}}]}}'
        )
        data = await self._llm_json(system, user)
        segments = []
        for s in data.get("segments", []):
            segments.append(Segment(
                index=s.get("index", len(segments)+1),
                description=s.get("description", ""),
                emotion=s.get("emotion", ""),
                action=s.get("action", ""),
                duration_seconds=s.get("duration_seconds", 5),
            ))
        logger.info(f"[SegmentAgent] Generated {len(segments)} segments")
        return segments

    # ─── Step 2: Shot Agent ─────────────────────────────────────────────

    async def _generate_shots(self, segments: list[Segment], style: str = "") -> list[Shot]:
        """Generate shot-by-shot prompts for each segment."""
        system = (
            "你是一个专业的AI分镜师，擅长为每个片段生成精确的镜头提示词。"
            "每个镜头的prompt应当包含：人物动作、场景环境、光影氛围、镜头角度。"
            "你的输出是严格的JSON。"
        )
        segments_str = json.dumps([asdict(s) for s in segments], ensure_ascii=False, indent=2)
        user = (
            f"为以下片段生成分镜。每个片段生成1-3个镜头。\n"
            f"风格：{style or '默认'}\n\n"
            f"片段数据：\n{segments_str}\n\n"
            f"输出JSON格式：\n"
            f'{{"shots": [{{"id": 1, "segment_index": 1, "prompt_zh": "镜头描述(中文)", '
            f'"prompt_en": "shot description(English)", "camera_angle": "特写/全景/中景", '
            f'"duration_seconds": 3}}]}}'
        )
        data = await self._llm_json(system, user)
        shots = []
        for s in data.get("shots", []):
            shots.append(Shot(
                id=s.get("id", len(shots)+1),
                segment_index=s.get("segment_index", 1),
                prompt_zh=s.get("prompt_zh", ""),
                prompt_en=s.get("prompt_en", ""),
                camera_angle=s.get("camera_angle", ""),
                duration_seconds=s.get("duration_seconds", 3),
            ))
        logger.info(f"[ShotAgent] Generated {len(shots)} shots")
        return shots

    # ─── Step 3: Asset Extraction ───────────────────────────────────────

    async def _extract_assets(self, script_text: str) -> list[Asset]:
        """Extract characters, props, and scenes from the script."""
        system = (
            "你是一个AI资产管理师，擅长从剧本中提取角色、道具和场景。"
            "你的输出是严格的JSON。"
        )
        user = (
            f"从以下剧本中提取所有出场的角色、关键道具和场景。\n\n"
            f"剧本：\n{script_text[:2000]}\n\n"
            f"输出JSON格式：\n"
            f'{{"assets": [{{"type": "character/prop/scene", "name": "名称", "description": "外貌/样式描述"}}]}}'
        )
        data = await self._llm_json(system, user)
        assets = []
        for a in data.get("assets", []):
            assets.append(Asset(
                type=a.get("type", "character"),
                name=a.get("name", ""),
                description=a.get("description", ""),
            ))
        logger.info(f"[AssetAgent] Extracted {len(assets)} assets")
        return assets

    # ─── Full Pipeline ──────────────────────────────────────────────────

    async def generate_episode(self, script_text: str, title: str = "Episode 1",
                               style: str = "", episode_index: int = 1) -> Episode:
        """
        Full storyboard generation pipeline:
          1. Extract assets (characters, props, scenes)
          2. Generate segments (起承转合 emotional arcs)
          3. Generate shots (shot-by-shot prompts for video generation)
          4. Package into structured Episode object
        """
        logger.info(f"[StoryboardAgent] Starting episode generation: {title}")

        # Run asset extraction and segment generation in parallel
        assets, segments = await asyncio.gather(
            self._extract_assets(script_text),
            self._generate_segments(script_text, style),
        )

        # Generate shots from segments
        shots = await self._generate_shots(segments, style)

        episode = Episode(
            title=title,
            episode_index=episode_index,
            assets=assets,
            segments=segments,
            shots=shots,
        )

        logger.info(f"[StoryboardAgent] Episode complete: {len(segments)} segments, "
                     f"{len(shots)} shots, {len(assets)} assets")
        return episode
