"""Data models for AI Content Strategy, audience targeting, and scene directing."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ContentFormat(str, Enum):
    EDUCATIONAL = "educational"
    EXPLAINER = "explainer"
    NEWS = "news"
    LIST = "list"
    STORY = "story"
    TUTORIAL = "tutorial"
    COMPARISON = "comparison"
    REACTION_DEBATE = "reaction_debate"


class HookType(str, Enum):
    CURIOSITY_GAP = "curiosity_gap"
    CONTRARIAN_BOLD = "contrarian_bold"
    STORY_IN_MEDIAS_RES = "story_in_medias_res"
    PROBLEM_AGITATION = "problem_agitation"
    STATISTIC_SHOCK = "statistic_shock"
    DIRECT_QUESTION = "direct_question"


class TargetAudience(str, Enum):
    TECH_ENTHUSIASTS = "tech_enthusiasts"
    PROFESSIONALS = "professionals"
    GENERAL_CONSUMERS = "general_consumers"
    STUDENTS_LEARNERS = "students_learners"
    CREATORS = "creators"


class ScenePlan(BaseModel):
    """Visual and directorial plan for an individual scene."""

    scene_number: int
    kind: str  # "hook" | "setup" | "point" | "evidence" | "payoff" | "cta"
    purpose: str = ""
    visual_style: str = "dynamic tech background"
    broll_keywords: list[str] = Field(default_factory=list)
    pacing: str = "steady"  # "fast" | "steady" | "dramatic"
    estimated_seconds: float = 5.0


class ContentStrategy(BaseModel):
    """Strategic blueprint guiding script synthesis and visual directing."""

    candidate_id: str
    topic: str
    content_format: ContentFormat = ContentFormat.EXPLAINER
    recommended_angle: str = ""
    target_audience: TargetAudience = TargetAudience.GENERAL_CONSUMERS
    hook_strategy: HookType = HookType.CURIOSITY_GAP
    hook_text_prompt: str = ""
    short_form_potential_score: float = 75.0
    scene_count: int = 3
    scene_plans: list[ScenePlan] = Field(default_factory=list)
    cta_strategy: str = "follow for daily breakdowns and save for later"
    target_duration_seconds: int = 35
    key_takeaways: list[str] = Field(default_factory=list)
    confidence_score: float = 0.85
    provider: str = "heuristic_strategist"
    notes: list[str] = Field(default_factory=list)

    def model_dump_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2, ensure_ascii=False)