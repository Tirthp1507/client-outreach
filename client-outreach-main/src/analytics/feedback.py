"""Additive performance-feedback scorer for ranking candidates without replacing the existing ranker.

Consumes the multipliers learned by :class:`PerformanceInsightsEngine` and
produces a bounded, explainable score adjustment for ungenerated candidates
based on what their *strategy* would be. It is purely additive: when no reliable
performance data exists it is a strict no-op (adjusted score == raw score).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Sequence

from analytics.insights import (
    DEFAULT_MAX_POINTS,
    DEFAULT_MIN_SAMPLES,
    PerformanceInsightsEngine,
)
from config import get_config
from processors.models import ProcessedCandidate

if TYPE_CHECKING:
    from db.database import Database

logger = logging.getLogger(__name__)


class PerformanceFeedbackScorer:
    """Adjusts candidate scores using learned performance correlations."""

    def __init__(
        self,
        db: Any | None = None,
        config: dict[str, Any] | None = None,
        *,
        min_samples: int | None = None,
        max_points: float | None = None,
    ) -> None:
        if db is None:
            from db.database import Database
            self.db = Database()
        else:
            self.db = db
        self.config = config or get_config()

        ana_cfg = self.config.get("analytics", {}) or {}
        self.min_samples = min_samples or int(ana_cfg.get("min_samples", DEFAULT_MIN_SAMPLES))
        self.max_points = float(max_points) if max_points is not None else float(
            ana_cfg.get("max_score_adjustment", DEFAULT_MAX_POINTS)
        )
        self.engine = PerformanceInsightsEngine(db=self.db, config=self.config)
        self._multipliers = self.engine.get_feedback_multipliers(
            min_samples=self.min_samples
        )
        self._strategist = None

    @property
    def has_signal(self) -> bool:
        """True when the underlying history produced at least one non-neutral multiplier."""
        return any(
            m != 1.0
            for dim_map in self._multipliers.values()
            for m in dim_map.values()
        )

    def _classify(self, candidate: ProcessedCandidate):
        """Determine the strategy that would be generated for this candidate."""
        if self._strategist is None:
            from strategy.topic_strategist import TopicStrategist

            self._strategist = TopicStrategist(self.config)
        try:
            return self._strategist.develop_strategy(candidate)
        except Exception as exc:
            logger.warning("Failed to develop strategy for feedback: %s", exc)
            return None

    @staticmethod
    def _categories_from_strategy(strategy) -> dict[str, str]:
        if strategy is None:
            return {}
        return {
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

    def explain(self, candidate: ProcessedCandidate) -> tuple[float, list[str]]:
        """Return (boost_points, explanation) for a candidate (boost >= 0 is not implied)."""
        strategy = self._classify(candidate)
        if strategy is None:
            return 0.0, []
        return self.engine.best_feedback_boost(
            self._categories_from_strategy(strategy),
            min_samples=self.min_samples,
            max_points=self.max_points,
        )

    def score(self, candidate: ProcessedCandidate) -> float:
        """Bounded additive score: raw candidate score plus the strongest learned signal."""
        boost, _ = self.explain(candidate)
        if boost == 0.0:
            return candidate.score
        return round(min(100.0, max(0.0, candidate.score + boost)), 1)

    def rerank(
        self, candidates: Sequence[ProcessedCandidate]
    ) -> list[tuple[ProcessedCandidate, float, list[str]]]:
        """Return candidates sorted by adjusted score with explanations."""
        scored = [(c, self.score(c), self.explain(c)[1]) for c in candidates]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored