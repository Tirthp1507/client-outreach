"""Content ranker and video-suitability scoring engine."""

from __future__ import annotations

import math
import re
from typing import Sequence

from collectors.models import RawContentItem

HOOK_PATTERNS = [
    (re.compile(r"\b(how to|why|what happens|the reason|secret|truth|revealed)\b", re.IGNORECASE), 12.0, "Curiosity hook keywords"),
    (re.compile(r"\b(top \d+|\d+ (ways|tips|hacks|rules|reasons|mistakes|tools|secrets))\b", re.IGNORECASE), 14.0, "Numbered listicle hook"),
    (re.compile(r"\b(never|stop|avoid|mistake|warning|worst)\b", re.IGNORECASE), 10.0, "Negative bias / warning hook"),
    (re.compile(r"\b(ai|chatgpt|automation|future|breakthrough|new|game-changer)\b", re.IGNORECASE), 8.0, "Trending tech / high-interest topic"),
    (re.compile(r"\?$", re.IGNORECASE), 6.0, "Question title prompt"),
]


class ContentRanker:
    """Ranks collected content items for short-form video suitability."""

    def score_item(self, item: RawContentItem, clean_body: str) -> tuple[float, dict[str, float], list[str]]:
        """Compute 0-100 suitability score, component breakdown, and reason list."""
        breakdown: dict[str, float] = {}
        reasons: list[str] = []

        # 1. Hook Potential (up to 35 pts)
        hook_score = 0.0
        for pattern, points, reason in HOOK_PATTERNS:
            if pattern.search(item.title):
                hook_score += points
                if reason not in reasons:
                    reasons.append(reason)
        hook_score = min(35.0, hook_score)
        if hook_score == 0.0:
            hook_score = 10.0  # baseline
        breakdown["hook_potential"] = round(hook_score, 1)

        # 2. Content Substance & Word Count (up to 25 pts)
        words = len(clean_body.split())
        if 30 <= words <= 350:
            substance_score = 25.0
            reasons.append("Ideal text length for a 30-50s script")
        elif 15 <= words < 30:
            substance_score = 15.0
            reasons.append("Concise prompt, suitable for concept expansion")
        elif words > 350:
            substance_score = 18.0
            reasons.append("Rich long-form content for summarization")
        else:
            substance_score = 8.0
        breakdown["content_substance"] = round(substance_score, 1)

        # 3. Engagement / Source Signal (up to 25 pts)
        if item.score > 0:
            engagement_score = min(25.0, math.log1p(item.score) * 3.5)
            if item.score > 50:
                reasons.append(f"High engagement signal ({int(item.score)} score)")
        else:
            engagement_score = 15.0  # baseline for curated feeds
        breakdown["engagement_signal"] = round(engagement_score, 1)

        # 4. Readability & Tags (up to 15 pts)
        readability = 10.0
        if item.tags:
            readability += 5.0
        breakdown["structure_bonus"] = round(min(15.0, readability), 1)

        total_score = min(100.0, sum(breakdown.values()))
        return round(total_score, 1), breakdown, reasons

    def rank_items(
        self,
        items: Sequence[tuple[RawContentItem, str]],
    ) -> list[tuple[RawContentItem, str, float, dict[str, float], list[str]]]:
        """Score and sort items descending by total score."""
        scored = []
        for item, clean_body in items:
            score, breakdown, reasons = self.score_item(item, clean_body)
            scored.append((item, clean_body, score, breakdown, reasons))

        scored.sort(key=lambda x: x[2], reverse=True)
        return scored