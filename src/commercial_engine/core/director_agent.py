"""
core/director_agent.py
======================
Creative director for the UGC pipeline.

This version keeps backward compatibility with the existing task pipeline while
adding:
- persona-aware planning
- sales-framework selection
- hook / angle variants
- richer segment blueprints for timeline generation
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from core.persona_engine import get_persona_definition
from core.sales_framework_engine import SalesFrameworkEngine
from core.variant_generator import VariantGenerator
from utils.logger import get_logger

logger = get_logger(__name__)

# --- Constants to eliminate magic numbers ---
A_ROLL_RATIO_PRESENTER = 0.42
A_ROLL_RATIO_NO_PRESENTER = 0.0

DEFAULT_VIDEO_DURATION = 30
SHORT_VIDEO_DURATION_THRESHOLD = 20
HOOK_DURATION_SHORT_VIDEO = 4
HOOK_DURATION_LONG_VIDEO = 5
CTA_DURATION = 4

DEFAULT_SELLING_POINTS = ["easy to use", "visible result", "daily friendly"]


MODEL_COSTS = {
    "seedance_15":    {"per_10s": 0.08,      "label": "Seedance 1.5 Pro"},
    "veo_31_fast":    {"per_video": 0.30,    "label": "Veo 3.1 Fast"},
    "veo_31_quality": {"per_video": 1.25,    "label": "Veo 3.1 Quality"},
    "runway":         {"per_5s": 0.06,       "label": "Runway"},
    "runway_1080p":   {"per_5s": 0.15,       "label": "Runway 1080p"},
    "sora_2":         {"per_10s": 0.175,     "label": "Sora 2"},
    "kling_26":       {"per_10s": 0.275,     "label": "Kling 2.6"},
    "kling_30":       {"per_s_1080p": 0.20,  "label": "Kling 3.0"},
    "hailuo":         {"per_6s": 0.15,       "label": "Hailuo 2.3"},
}

BUDGET_TIERS = {
    "economy": {"max_usd": 0.60, "preferred_models": ["seedance_15", "runway"]},
    "premium": {"max_usd": 2.50, "preferred_models": ["veo_31_fast", "seedance_15"]},
    "china":   {"max_usd": 1.50, "preferred_models": ["kling_30", "hailuo", "seedance_15"]},
}

FRAMEWORK_TO_STRATEGY = {
    "pas": "testimonial_demo_hybrid",
    "comparison": "comparison_challenge",
    "testimonial": "testimonial_demo_hybrid",
    "problem_solution_proof": "tutorial_walkthrough",
    "aida": "aspirational_lifestyle",
}


@dataclass
class ProductionPlan:
    strategy: str
    video_model: str
    platform: str
    persona: str
    hook_style: str
    tone_style: str
    cta_style: str
    primary_language: str
    total_duration: int
    a_roll_ratio: float
    b_roll_ratio: float
    estimated_cost_usd: float
    segments_json: list[dict] = field(default_factory=list)
    cta_segment: dict = field(default_factory=dict)
    selected_framework: str = ""
    selected_variant_id: str = ""
    variants: list[dict] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    raw_json: str = ""

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "video_model": self.video_model,
            "platform": self.platform,
            "persona": self.persona,
            "hook_style": self.hook_style,
            "tone_style": self.tone_style,
            "cta_style": self.cta_style,
            "primary_language": self.primary_language,
            "total_duration": self.total_duration,
            "a_roll_ratio": self.a_roll_ratio,
            "b_roll_ratio": self.b_roll_ratio,
            "estimated_cost_usd": self.estimated_cost_usd,
            "segments": self.segments_json,
            "cta_segment": self.cta_segment,
            "selected_framework": self.selected_framework,
            "selected_variant_id": self.selected_variant_id,
            "variants": self.variants,
            "reasoning": self.reasoning,
        }


# --- Strategy Pattern for Segment Building ---
class SegmentBuilderStrategy:
    """Base strategy for building video segments."""
    def __init__(self, language: str, persona, product_name: str):
        self.language = language
        self.persona = persona
        self.product_name = product_name

    def build_hook(self, idx: int, duration: int, hook_line: str) -> dict:
        raise NotImplementedError

    def build_body_beat(self, idx: int, duration: int, beat_name: str, point: str, action: str) -> dict:
        raise NotImplementedError

    def build_cta(self, idx: int, duration: int, cta_line: str) -> dict:
        raise NotImplementedError

    def _overlay_from_point(self, point: str) -> str:
        point = (point or "").strip()
        if not point:
            return ""
        words = point.split()
        if len(words) <= 5:
            return point
        return " ".join(words[:5])

    def _default_hook_overlay(self) -> str:
        lang = (self.language or "en").lower()
        if lang == "it": return "Da provare"
        if lang == "zh": return "真的有感"
        return "Worth trying"

    def _default_cta_overlay(self) -> str:
        lang = (self.language or "en").lower()
        if lang == "it": return "Scoprilo ora"
        if lang == "zh": return "现在去看看"
        return "Check it out"


class PresenterSegmentBuilder(SegmentBuilderStrategy):
    """Segment builder when a presenter (A-roll) is available."""
    def build_hook(self, idx: int, duration: int, hook_line: str) -> dict:
        shot_type = self.persona.recommended_shot_types[0] if self.persona.recommended_shot_types else "selfie_closeup"
        return {
            "id": f"seg_{idx:02d}",
            "track": "a_roll",
            "duration": duration,
            "spoken_line": hook_line,
            "emotion": "surprised_authentic",
            "shot_type": shot_type,
            "overlay_text": self._default_hook_overlay(),
            "scene_purpose": "hook",
        }

    def build_body_beat(self, idx: int, duration: int, beat_name: str, point: str, action: str) -> dict:
        if beat_name in {"problem", "proof"}:
            spoken = self._localized_spoken_line(beat_name, point)
            emotion = "warm_casual" if beat_name == "problem" else "confident_expert"
            shot_index = 0 if beat_name == "problem" else min(1, len(self.persona.recommended_shot_types)-1)
            shot_type = self.persona.recommended_shot_types[min(len(self.persona.recommended_shot_types)-1, shot_index)] if self.persona.recommended_shot_types else "half_body_talk"
            return {
                "id": f"seg_{idx:02d}",
                "track": "a_roll",
                "duration": duration,
                "spoken_line": spoken,
                "emotion": emotion,
                "shot_type": shot_type,
                "overlay_text": self._overlay_from_point(point),
                "scene_purpose": beat_name,
            }
        else:
            return {
                "id": f"seg_{idx:02d}",
                "track": "b_roll",
                "duration": duration,
                "visual_goal": beat_name,
                "product_action": action,
                "shot_type": action,
                "overlay_text": self._overlay_from_point(point),
                "scene_purpose": beat_name,
            }

    def build_cta(self, idx: int, duration: int, cta_line: str) -> dict:
        shot_type = self.persona.recommended_shot_types[0] if self.persona.recommended_shot_types else "selfie_closeup"
        return {
            "id": f"seg_{idx:02d}",
            "track": "a_roll",
            "duration": duration,
            "spoken_line": cta_line,
            "emotion": "clear_confident",
            "shot_type": shot_type,
            "overlay_text": self._default_cta_overlay(),
            "scene_purpose": "cta",
        }

    def _localized_spoken_line(self, beat_name: str, point: str) -> str:
        lang = (self.language or "en").lower()
        if lang == "it":
            if beat_name == "problem": return f"Mi piace perché risolve un problema vero: {point}."
            if beat_name == "solution": return f"Nell'uso quotidiano, {self.product_name} rende tutto più semplice."
            if beat_name == "proof": return f"La parte che noto di più è questa: {point}."
            return f"{self.product_name} si inserisce bene nella routine."
        if lang == "zh":
            if beat_name == "problem": return f"我最在意的一点其实就是：{point}。"
            if beat_name == "solution": return f"真正用起来的时候，它会让整个过程更顺手。"
            if beat_name == "proof": return f"我觉得最有说服力的，还是这个细节：{point}。"
            return f"{self.product_name} 很适合日常使用。"
        if beat_name == "problem": return f"The main thing I care about is {point}."
        if beat_name == "solution": return f"In real use, {self.product_name} just makes the routine easier."
        if beat_name == "proof": return f"The detail that really sold me is this: {point}."
        return f"{self.product_name} fits into daily use really naturally."


class BRollSegmentBuilder(SegmentBuilderStrategy):
    """Segment builder when no presenter is available (pure B-roll)."""
    def build_hook(self, idx: int, duration: int, hook_line: str) -> dict:
        return {
            "id": f"seg_{idx:02d}",
            "track": "b_roll",
            "duration": duration,
            "visual_goal": "product_reveal",
            "product_action": "unbox",
            "shot_type": "product_reveal",
            "overlay_text": self._default_hook_overlay(),
            "scene_purpose": "hook",
        }

    def build_body_beat(self, idx: int, duration: int, beat_name: str, point: str, action: str) -> dict:
        return {
            "id": f"seg_{idx:02d}",
            "track": "b_roll",
            "duration": duration,
            "visual_goal": beat_name,
            "product_action": action,
            "shot_type": action,
            "overlay_text": self._overlay_from_point(point),
            "scene_purpose": beat_name,
        }

    def build_cta(self, idx: int, duration: int, cta_line: str) -> dict:
        return {
            "id": f"seg_{idx:02d}",
            "track": "b_roll",
            "duration": duration,
            "visual_goal": "cta_product_hold",
            "product_action": "result_reveal",
            "shot_type": "hero_hold",
            "overlay_text": self._default_cta_overlay(),
            "scene_purpose": "cta",
        }


class UGCProducer:
    def __init__(self, config: dict):
        self.config = config
        self._decisions: list[str] = []
        self.sales_engine = SalesFrameworkEngine()
        self.variant_generator = VariantGenerator()

    async def build_plan(
        self,
        product_summary: str,
        request,
        presenter_profile,
    ) -> ProductionPlan:
        has_presenter = bool(
            getattr(presenter_profile, "face_image_path", None)
            and getattr(presenter_profile, "lipsync_model", "none") != "none"
        )
        return self._rule_based_plan(
            request=request,
            presenter_profile=presenter_profile,
            has_presenter=has_presenter,
            product_summary=product_summary,
        )

    def _rule_based_plan(
        self,
        request,
        presenter_profile,
        has_presenter: bool,
        product_summary: str,
    ) -> ProductionPlan:
        language = (getattr(request, "language", "it") or "it").split(",")[0]
        persona = get_persona_definition(
            getattr(request, "persona_template", None) or getattr(presenter_profile, "persona_template", None),
            language,
        )
        tier = getattr(request, "quality_tier", "economy")
        model = self._resolve_model(tier, getattr(request, "model", "auto"))
        duration = int(getattr(request, "duration", DEFAULT_VIDEO_DURATION) or DEFAULT_VIDEO_DURATION)
        platform = getattr(request, "platform", "douyin")
        
        selling_points = []
        # pull hints from request/product_summary when available
        if hasattr(request, "text_prompt") and request.text_prompt:
            product_name = request.text_prompt[:60]
        else:
            product_name = "this product"
            
        if isinstance(product_summary, str):
            product_name = product_summary.split(".")[0][:80] or product_name
            # naive extraction of selling-points fragment
            if "Selling points:" in product_summary:
                points_text = product_summary.split("Selling points:", 1)[1]
                selling_points = [p.strip(" .") for p in points_text.split(",") if p.strip()][:5]

        hook_style = getattr(request, "hook_style", "") or (persona.preferred_hook_styles[0] if persona.preferred_hook_styles else "result_first")
        framework = self.sales_engine.choose_framework(
            product_category=getattr(request, "video_goal", "") or "",
            platform=platform,
            has_presenter=has_presenter,
            explicit_hook_style=hook_style,
        )
        sales_plan = self.sales_engine.build(
            framework=framework,
            product_name=product_name,
            selling_points=selling_points,
            target_audience=getattr(request, "target_audience", "") or "",
            use_case=getattr(request, "video_goal", "") or "",
            language=language,
        )
        variants = self.variant_generator.build_batch_variants(
            language=language,
            product_name=product_name,
            selling_points=selling_points,
            preferred_styles=list(dict.fromkeys([hook_style] + list(getattr(presenter_profile, "preferred_hook_styles", []) or []) + list(persona.preferred_hook_styles))),
            max_variants=int(getattr(request, "batch_variants", 6) or 6),
        )
        best_variant = variants[0]
        best_variant.framework = framework

        a_ratio = A_ROLL_RATIO_PRESENTER if has_presenter else A_ROLL_RATIO_NO_PRESENTER
        b_ratio = round(1.0 - a_ratio, 2)
        segments = self._build_segments(
            duration=duration,
            language=language,
            has_presenter=has_presenter,
            persona=persona,
            sales_plan=sales_plan,
            hook_line=best_variant.hook_line,
            product_name=product_name,
            selling_points=selling_points,
        )
        reasoning = [
            f"persona={persona.persona_id}",
            f"framework={framework}",
            f"hook={best_variant.hook_style}",
            f"has_presenter={has_presenter}",
            f"model={model}",
        ]
        cost = self._estimate_cost(model, duration)
        
        # Build CTA overlay segment payload using strategy pattern
        builder = PresenterSegmentBuilder(language, persona, product_name) if has_presenter else BRollSegmentBuilder(language, persona, product_name)
        
        return ProductionPlan(
            strategy=FRAMEWORK_TO_STRATEGY.get(framework, "testimonial_demo_hybrid"),
            video_model=model,
            platform=platform,
            persona=persona.persona_id,
            hook_style=best_variant.hook_style,
            tone_style=getattr(request, "tone_style", "") or persona.emotional_tone or "authentic_friend",
            cta_style=getattr(request, "cta_style", "") or persona.cta_style or "link_in_bio",
            primary_language=language,
            total_duration=duration,
            a_roll_ratio=a_ratio,
            b_roll_ratio=b_ratio,
            estimated_cost_usd=cost,
            segments_json=segments,
            cta_segment={
                "spoken_line": sales_plan.cta_line,
                "overlay_text": builder._default_cta_overlay(),
            },
            selected_framework=framework,
            selected_variant_id=best_variant.variant_id,
            variants=[{
                "variant_id": v.variant_id,
                "angle_name": v.angle_name,
                "hook_style": v.hook_style,
                "hook_line": v.hook_line,
                "score_hint": v.score_hint,
                "hook_score": v.hook_score,
                "notes": v.notes,
            } for v in variants],
            reasoning=reasoning,
        )

    def _build_segments(
        self,
        duration: int,
        language: str,
        has_presenter: bool,
        persona,
        sales_plan,
        hook_line: str,
        product_name: str,
        selling_points: list[str],
    ) -> list[dict]:
        """Constructs the timeline segments using the appropriate strategy generator."""
        points = selling_points or sales_plan.proof_points or DEFAULT_SELLING_POINTS
        
        hook_duration = HOOK_DURATION_SHORT_VIDEO if duration <= SHORT_VIDEO_DURATION_THRESHOLD else HOOK_DURATION_LONG_VIDEO
        remaining_duration = max(0, duration - hook_duration - CTA_DURATION)
        
        beat_durations = self._split_middle_duration(remaining_duration)
        beat_templates = [
            ("problem", points[0], "pain_point"),
            ("solution", points[min(1, len(points)-1)], "usage_demo"),
            ("proof", points[min(2, len(points)-1)], "result_reveal"),
        ]
        
        builder = PresenterSegmentBuilder(language, persona, product_name) if has_presenter else BRollSegmentBuilder(language, persona, product_name)

        segments = []
        idx = 1
        
        # 1. Hook Segment
        segments.append(builder.build_hook(idx, hook_duration, hook_line))
        idx += 1

        # 2. Body Segments (Problem, Solution, Proof)
        for beat_duration, (beat_name, point, action) in zip(beat_durations, beat_templates):
            if beat_duration <= 0:
                continue
            segments.append(builder.build_body_beat(idx, beat_duration, beat_name, point, action))
            idx += 1

        # 3. CTA Segment
        segments.append(builder.build_cta(idx, CTA_DURATION, sales_plan.cta_line))

        return segments

    def _split_middle_duration(self, remaining: int) -> list[int]:
        if remaining <= 0:
            return []
        if remaining <= 6:
            return [remaining]
        if remaining <= 12:
            a = remaining // 2
            return [a, remaining - a]
        base = [remaining // 3] * 3
        for i in range(remaining - sum(base)):
            base[i % 3] += 1
        return base

    def _resolve_model(self, tier: str, explicit_model: Optional[str]) -> str:
        if explicit_model and explicit_model not in {"", "auto"}:
            return explicit_model
        return BUDGET_TIERS.get(tier, BUDGET_TIERS["economy"])["preferred_models"][0]

    def _estimate_cost(self, model: str, duration_seconds: int) -> float:
        spec = MODEL_COSTS.get(model, {})
        if "per_video" in spec:
            return float(spec["per_video"])
        if "per_10s" in spec:
            return round((duration_seconds / 10.0) * spec["per_10s"], 4)
        if "per_5s" in spec:
            return round((duration_seconds / 5.0) * spec["per_5s"], 4)
        if "per_6s" in spec:
            return round((duration_seconds / 6.0) * spec["per_6s"], 4)
        if "per_s_1080p" in spec:
            return round(duration_seconds * spec["per_s_1080p"], 4)
        return 0.0

