"""AI Topic Strategist determining content potential, angle, format, audience, and scene plans."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from processors.models import ProcessedCandidate
from strategy.models import (
    ContentFormat,
    ContentStrategy,
    HookType,
    ScenePlan,
    TargetAudience,
)

logger = logging.getLogger(__name__)

# Keywords for format classification
NEWS_KEYWORDS = {"settle", "billion", "million", "senate", "lawsuit", "court", "probe", "ban", "break", "un", "deal", "fed", "investigation", "claims"}
LIST_KEYWORDS = {"top", "reasons", "hacks", "tips", "tools", "ways", "methods", "rules", "steps"}
TUTORIAL_KEYWORDS = {"how", "guide", "tutorial", "build", "create", "fix", "setup", "master"}
COMPARISON_KEYWORDS = {"vs", "versus", "better", "compare", "difference", "against"}
STORY_KEYWORDS = {"history", "origin", "founded", "truth", "behind", "secret", "rise", "fall"}


class TopicStrategist:
    """Analyzes processed content candidates and synthesizes actionable content strategies."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        performance_feedback: bool | None = None,
        feedback_db=None,
    ) -> None:
        self.config = config or {}
        strat_cfg = self.config.get("strategy", {}) or {}
        self.default_duration = int(strat_cfg.get("target_duration_seconds", 35))
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        # Phase 9: optional additive performance feedback. Off by default so the
        # deterministic heuristic strategy system is never changed implicitly.
        if performance_feedback is None:
            performance_feedback = bool(strat_cfg.get("performance_feedback", False))
        self.performance_feedback = performance_feedback
        self.feedback_db = feedback_db
        # Phase 10: optional visual/template diversity rotation. Off by default.
        self.diversity_rotation = bool(strat_cfg.get("diversity_rotation", False))

    def develop_strategy(
        self,
        candidate: ProcessedCandidate,
        *,
        advance_rotation: bool = False,
    ) -> ContentStrategy:
        """Generate a complete strategic content plan for a candidate.

        ``advance_rotation`` is True only on the actual generation path (see
        ``generators/bridge.py``) so visual-variant rotation never advances
        during selection/scoring passes.
        """
        # Check if OpenAI strategy is enabled and configured
        if self.openai_api_key and self.config.get("strategy", {}).get("provider") == "openai":
            try:
                ai_strat = self._develop_strategy_ai(candidate)
                if ai_strat:
                    strategy = ai_strat
                else:
                    strategy = self._develop_strategy_heuristic(candidate)
            except Exception as exc:
                logger.warning("AI strategist failed, falling back to heuristics: %s", exc)
                strategy = self._develop_strategy_heuristic(candidate)
        else:
            strategy = self._develop_strategy_heuristic(candidate)

        if self.performance_feedback:
            self._apply_performance_feedback(strategy)
        if self.diversity_rotation and advance_rotation:
            self._apply_rotation(strategy)
        return strategy

    def _apply_performance_feedback(self, strategy: ContentStrategy) -> ContentStrategy:
        """Additively nudge strategy potential score from learned performance multipliers."""
        try:
            from analytics.insights import PerformanceInsightsEngine

            engine = PerformanceInsightsEngine(db=self.feedback_db, config=self.config)
            categories = {
                "content_format": strategy.content_format.value,
                "hook_strategy": strategy.hook_strategy.value,
                "target_audience": strategy.target_audience.value,
                "topic_pattern": PerformanceInsightsEngine.classify_topic_pattern(strategy.topic),
                "scene_count": PerformanceInsightsEngine.bucket_scenes(len(strategy.scene_plans)),
                "target_duration": PerformanceInsightsEngine.bucket_duration(
                    strategy.target_duration_seconds
                ),
                "cta_strategy": PerformanceInsightsEngine.classify_cta(strategy.cta_strategy),
            }
            boost, reasons = engine.best_feedback_boost(categories)
            if boost == 0.0:
                return strategy

            previous = strategy.short_form_potential_score
            strategy.short_form_potential_score = round(
                min(100.0, max(0.0, previous + float(boost))), 1
            )
            strategy.notes.append("Performance feedback: " + "; ".join(reasons))
            strategy.notes.append(
                f"Potential score adjusted from {previous:g} to "
                f"{strategy.short_form_potential_score:g} by learned performance."
            )
        except Exception as exc:
            logger.warning("Performance feedback unavailable, strategy unchanged: %s", exc)
        return strategy

    def _apply_rotation(self, strategy: ContentStrategy) -> ContentStrategy:
        """Phase 10 visual/template rotation: restyle scene plans from the next variant."""
        try:
            from strategy.rotation import TemplateRotation

            rotation = TemplateRotation(config=self.config)
            variant = rotation.next_variant()
            palette, pace, template = variant["palette"], variant["pace"], variant["template"]

            for scene in strategy.scene_plans:
                base = scene.visual_style or ""
                scene.visual_style = f"{palette} palette | {base}" if base else f"{palette} palette"
                if scene.kind in ("setup", "point"):
                    scene.pacing = pace
                elif scene.kind == "hook":
                    scene.pacing = "fast"

            strategy.notes.append(
                f"Visual template rotation #{rotation.state['turns']}: variant "
                f"{variant['tag']!r} ({palette}, {pace}, {template})."
            )
        except Exception as exc:
            logger.warning("Visual rotation unavailable, strategy unchanged: %s", exc)
        return strategy

    def _develop_strategy_heuristic(self, candidate: ProcessedCandidate) -> ContentStrategy:
        """Offline deterministic heuristic content strategist."""
        title_lower = (candidate.clean_title or candidate.raw_title).lower()
        title_words = set(re.findall(r"\b\w+\b", title_lower))

        # 1. Determine Content Format & Audience
        if title_words & NEWS_KEYWORDS:
            fmt = ContentFormat.NEWS
            hook_type = HookType.STATISTIC_SHOCK if any(w in title_words for w in {"billion", "million", "pay"}) else HookType.CURIOSITY_GAP
            audience = TargetAudience.GENERAL_CONSUMERS
            angle = f"The real breakdown behind the headlines on {candidate.clean_title}"
        elif title_words & LIST_KEYWORDS or re.search(r"\b\d+\b", title_lower):
            fmt = ContentFormat.LIST
            hook_type = HookType.CONTRARIAN_BOLD
            audience = TargetAudience.TECH_ENTHUSIASTS
            angle = f"The essential list you need to know about {candidate.clean_title}"
        elif title_words & TUTORIAL_KEYWORDS:
            fmt = ContentFormat.TUTORIAL
            hook_type = HookType.PROBLEM_AGITATION
            audience = TargetAudience.STUDENTS_LEARNERS
            angle = f"Step-by-step masterclass on {candidate.clean_title}"
        elif title_words & COMPARISON_KEYWORDS:
            fmt = ContentFormat.COMPARISON
            hook_type = HookType.DIRECT_QUESTION
            audience = TargetAudience.PROFESSIONALS
            angle = f"The direct comparison on {candidate.clean_title}"
        elif title_words & STORY_KEYWORDS:
            fmt = ContentFormat.STORY
            hook_type = HookType.STORY_IN_MEDIAS_RES
            audience = TargetAudience.GENERAL_CONSUMERS
            angle = f"The untold story behind {candidate.clean_title}"
        else:
            fmt = ContentFormat.EXPLAINER
            hook_type = HookType.CURIOSITY_GAP
            audience = TargetAudience.GENERAL_CONSUMERS
            angle = f"Why everyone is talking about {candidate.clean_title}"

        # 2. Hook Prompt
        hook_prompt = f"Punchy 3-second {hook_type.value} hook addressing {audience.value}"

        # 3. Calculate Potential Score (0-100)
        base_potential = candidate.score * 0.7 + 30.0
        if fmt in (ContentFormat.NEWS, ContentFormat.LIST):
            base_potential += 5.0
        potential_score = min(98.0, max(40.0, base_potential))

        # 4. Generate Scene Plans
        extract_keywords = [w for w in re.findall(r"\b\w{4,}\b", title_lower) if w not in {"with", "that", "this", "from"}]
        broll_kws = extract_keywords[:4]

        scene_plans = [
            ScenePlan(
                scene_number=1,
                kind="hook",
                purpose="Stop the scroll in first 3 seconds",
                visual_style="High-energy headline pop with bold typography and alert accents",
                broll_keywords=broll_kws[:2] or ["tech", "news"],
                pacing="fast",
                estimated_seconds=4.5,
            ),
            ScenePlan(
                scene_number=2,
                kind="setup",
                purpose="Contextualize the core situation and stakes",
                visual_style="Clean data graphic / context B-roll showing key parties and facts",
                broll_keywords=broll_kws[1:3] or ["cyber", "code"],
                pacing="steady",
                estimated_seconds=12.0,
            ),
            ScenePlan(
                scene_number=3,
                kind="point",
                purpose="Deliver the key facts and biggest takeaway",
                visual_style="Dynamic zoomed visual showcasing key impact / evidence",
                broll_keywords=broll_kws[2:4] or ["technology", "analysis"],
                pacing="steady",
                estimated_seconds=12.0,
            ),
            ScenePlan(
                scene_number=4,
                kind="cta",
                purpose="Call to action for engagement and comments",
                visual_style="Sleek modern outro with social follow prompts and discussion invite",
                broll_keywords=["community", "social"],
                pacing="steady",
                estimated_seconds=4.5,
            ),
        ]

        takeaways = [
            candidate.summary or candidate.clean_title,
            f"Source coverage by {candidate.source_name}",
        ]

        return ContentStrategy(
            candidate_id=candidate.id,
            topic=candidate.clean_title,
            content_format=fmt,
            recommended_angle=angle,
            target_audience=audience,
            hook_strategy=hook_type,
            hook_text_prompt=hook_prompt,
            short_form_potential_score=round(potential_score, 1),
            scene_count=len(scene_plans),
            scene_plans=scene_plans,
            cta_strategy="Save this for later and share your thoughts in the comments",
            target_duration_seconds=self.default_duration,
            key_takeaways=takeaways,
            confidence_score=0.90,
            provider="heuristic_strategist",
            notes=[f"Classified as {fmt.value} based on title keywords"],
        )

    def _develop_strategy_ai(self, candidate: ProcessedCandidate) -> ContentStrategy | None:
        """Call OpenAI-compatible endpoint for deep strategic analysis."""
        # Reserved for LLM API when configured
        return None