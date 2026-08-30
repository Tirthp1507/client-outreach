"""Strategy-directed script synthesis matching content formats and scene blueprints."""

from __future__ import annotations

import re
from typing import Any

from generators.models import Scene, ScriptSegment, ShortScript
from processors.models import ProcessedCandidate
from strategy.models import ContentFormat, ContentStrategy, HookType


class StrategyDirector:
    """Directs short video script writing based on strategic angle and format."""

    @classmethod
    def direct_script(
        cls,
        candidate: ProcessedCandidate,
        strategy: ContentStrategy,
        *,
        provider_name: str = "strategy_director",
    ) -> ShortScript:
        """Synthesize a complete multi-scene script directed by ContentStrategy."""
        topic_title = candidate.clean_title or candidate.raw_title
        core_body = candidate.clean_body or candidate.summary or topic_title

        # Clean core body into distinct clean sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", core_body) if len(s.strip()) > 15]
        if not sentences:
            sentences = [f"Here are the facts: {topic_title}."]

        # 1. Synthesize Hook matching hook_strategy
        hook_text = cls._synthesize_hook(topic_title, strategy.hook_strategy, sentences[0])

        # 2. Synthesize Main Story / Content Points
        main_points = cls._synthesize_main_points(strategy.content_format, sentences)

        # 3. Synthesize CTA matching cta_strategy
        cta_text = cls._synthesize_cta(strategy.cta_strategy, strategy.content_format)

        # 4. Construct Segments & Scenes
        hook_plan = strategy.scene_plans[0] if strategy.scene_plans else None
        main_plans = strategy.scene_plans[1:-1] if len(strategy.scene_plans) > 2 else []
        cta_plan = strategy.scene_plans[-1] if strategy.scene_plans else None

        segments = [
            ScriptSegment(
                kind="hook",
                text=hook_text,
                visual_prompt=hook_plan.visual_style if hook_plan else f"Dramatic hook visual on {topic_title}",
                broll_keywords=hook_plan.broll_keywords if hook_plan else ["news", "tech"],
                tone="urgent" if strategy.content_format == ContentFormat.NEWS else "engaging",
                transition="fade",
            ),
            ScriptSegment(
                kind="main",
                text=main_points,
                visual_prompt=main_plans[0].visual_style if main_plans else f"Dynamic contextual B-roll for {topic_title}",
                broll_keywords=main_plans[0].broll_keywords if main_plans else ["data", "screen"],
                tone="informative",
                transition="fade",
            ),
            ScriptSegment(
                kind="cta",
                text=cta_text,
                visual_prompt=cta_plan.visual_style if cta_plan else "Sleek animated outro card with discussion prompt",
                broll_keywords=cta_plan.broll_keywords if cta_plan else ["social", "follow"],
                tone="compelling",
                transition="fade",
            ),
        ]

        # Explicit Scene objects
        scenes: list[Scene] = []
        for idx, plan in enumerate(strategy.scene_plans, start=1):
            if plan.kind == "hook":
                s_narr = hook_text
            elif plan.kind == "cta":
                s_narr = cta_text
            else:
                s_narr = sentences[min(idx - 2, len(sentences) - 1)] if sentences else main_points

            scenes.append(
                Scene(
                    scene_index=idx,
                    kind=plan.kind,
                    narration=s_narr,
                    visual_description=plan.visual_style,
                    broll_keywords=plan.broll_keywords,
                    transition="fade",
                    estimated_duration=plan.estimated_seconds,
                )
            )

        provenance = {
            "candidate_id": candidate.id,
            "source_name": candidate.source_name,
            "source_url": candidate.source_url,
            "raw_title": candidate.raw_title,
            "clean_title": candidate.clean_title,
            "score": candidate.score,
            "score_reasons": candidate.reasons,
        }

        return ShortScript(
            topic=candidate.topic_suggestion or topic_title,
            title=topic_title,
            segments=segments,
            scenes=scenes,
            target_seconds=strategy.target_duration_seconds,
            provider=provider_name,
            provenance=provenance,
            strategy=strategy.model_dump(mode="json"),
        )

    @classmethod
    def _synthesize_hook(cls, title: str, hook_type: HookType, first_sentence: str) -> str:
        clean_t = cls._shorten_title(title)
        if hook_type == HookType.STATISTIC_SHOCK:
            # Prefer a real statistic drawn from the source text, then the title.
            num_match = re.search(r"(\$?\d+[\d,.]*\s*(?:billion|million|k|%|trillion|x)?)", first_sentence + " " + clean_t, re.IGNORECASE)
            if num_match:
                return f"{num_match.group(1)} — that's the number behind {clean_t}, and nobody talks about it."
            return f"There's a number behind {clean_t} most people never see. Here it is."
        if hook_type == HookType.CONTRARIAN_BOLD:
            return f"Forget everything you've heard about {clean_t}. The real story is the opposite."
        if hook_type == HookType.PROBLEM_AGITATION:
            return f"You're losing time every week because of {clean_t} — and it stops today."
        if hook_type == HookType.DIRECT_QUESTION:
            return f"Is {clean_t} actually worth it, or just overhyped? Let's find out."
        if hook_type == HookType.STORY_IN_MEDIAS_RES:
            return f"This week, {clean_t} flipped the whole playbook — here's what happened."
        # Default Curiosity Gap / Explainer
        return f"The truth about {clean_t} is hiding in plain sight. Here is the part nobody screenshots."

    @staticmethod
    def _shorten_title(title: str, max_words: int = 7) -> str:
        words = title.split()
        if not words:
            return title
        if len(words) <= max_words:
            return title.strip().rstrip(".!?")
        return " ".join(words[:max_words]).rstrip(".,;:") + "..."

    @classmethod
    def _synthesize_main_points(cls, fmt: ContentFormat, sentences: list[str]) -> str:
        body = " ".join(sentences[:2])
        if fmt == ContentFormat.LIST:
            first_p = sentences[0]
            second_p = sentences[1] if len(sentences) > 1 else "key developments are continuing to unfold."
            return f"Here is the breakdown: First, {first_p} Second, {second_p}"
        if fmt == ContentFormat.NEWS:
            return f"Here are the confirmed facts: {body}"
        if fmt == ContentFormat.TUTORIAL:
            return f"Here is the exact breakdown: {body}"
        return f"Here is the story: {body}"

    @classmethod
    def _synthesize_cta(cls, cta_strategy: str, fmt: ContentFormat) -> str:
        if fmt == ContentFormat.NEWS:
            return "Save this to stay ahead of the curve, follow for daily breakdowns, and drop your take below."
        if fmt == ContentFormat.LIST or fmt == ContentFormat.TUTORIAL:
            return "Bookmark this guide for later, follow for daily insights, and let me know your thoughts."
        return "Save this for later, follow for daily insights, and share this with someone who needs to see it."