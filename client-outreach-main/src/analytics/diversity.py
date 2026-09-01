"""Topic-fatigue / anti-repetition diversity scorer for long-running automation.

Phase 10 "content diversity" guard: dampens candidates whose topic or would-be
strategy categories repeat the recent production window. It is purely additive
(penalties only, bounded by a max) and stateless per call (derived from the
existing DB job history), so it behaves identically across daemon restarts.
It never replaces the deterministic ranker.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Sequence

from analytics.insights import PerformanceInsightsEngine
from config import get_config
from db.models import JobRecord
from processors.models import ProcessedCandidate

if TYPE_CHECKING:
    from db.database import Database

logger = logging.getLogger(__name__)

DEFAULT_WINDOW = 6
DEFAULT_TOPIC_SIM_THRESHOLD = 0.35
DEFAULT_TOPIC_SIM_PENALTY = 3.0
DEFAULT_FATIGUE_THRESHOLD = 2
DEFAULT_FATIGUE_PENALTY = 2.0
DEFAULT_MAX_TOTAL_PENALTY = 5.0

# Small closed-set of uninformative words excluded from topic token sets.
_STOPWORDS = {
    "with", "that", "this", "from", "and", "the", "for", "how", "why",
    "what", "your", "you", "are", "was", "were", "has", "have", "its",
    "than", "they", "them", "into", "over", "after",
}


class DiversityScorer:
    """Additive candidate scorer that penalizes thematic and categorical repetition."""

    def __init__(
        self,
        db: Any | None = None,
        config: dict[str, Any] | None = None,
        *,
        window: int | None = None,
        topic_sim_threshold: float | None = None,
        topic_sim_penalty: float | None = None,
        fatigue_threshold: int | None = None,
        fatigue_penalty: float | None = None,
        max_total_penalty: float | None = None,
    ) -> None:
        if db is None:
            from db.database import Database
            self.db = Database()
        else:
            self.db = db
        self.config = config or get_config()
        ana_cfg = self.config.get("analytics", {}) or {}
        self.window = window or int(ana_cfg.get("diversity_window", DEFAULT_WINDOW))
        self.topic_sim_threshold = (
            float(topic_sim_threshold)
            if topic_sim_threshold is not None
            else float(ana_cfg.get("diversity_topic_similarity", DEFAULT_TOPIC_SIM_THRESHOLD))
        )
        self.topic_sim_penalty = (
            float(topic_sim_penalty)
            if topic_sim_penalty is not None
            else float(ana_cfg.get("diversity_topic_penalty", DEFAULT_TOPIC_SIM_PENALTY))
        )
        self.fatigue_threshold = (
            int(fatigue_threshold)
            if fatigue_threshold is not None
            else int(ana_cfg.get("diversity_fatigue_threshold", DEFAULT_FATIGUE_THRESHOLD))
        )
        self.fatigue_penalty = (
            float(fatigue_penalty)
            if fatigue_penalty is not None
            else float(ana_cfg.get("diversity_fatigue_penalty", DEFAULT_FATIGUE_PENALTY))
        )
        self.max_total_penalty = (
            float(max_total_penalty)
            if max_total_penalty is not None
            else float(ana_cfg.get("max_diversity_penalty", DEFAULT_MAX_TOTAL_PENALTY))
        )
        self._strategist = None
        self._history: list[JobRecord] = self._recent_jobs(self.window)

    # -- recent production window -------------------------------------------

    def _recent_jobs(self, window: int) -> list[JobRecord]:
        try:
            jobs = self.db.list_jobs(limit=max(200, window * 4))
        except Exception as exc:
            logger.warning("DiversityScorer could not read job history: %s", exc)
            return []
        jobs = sorted(jobs, key=lambda j: j.created_at or "", reverse=True)
        return jobs[:window]

    @property
    def is_active(self) -> bool:
        """True when there is any local history to compare against."""
        return len(self._history) > 0

    @property
    def has_signal(self) -> bool:
        return self.is_active

    # -- topic similarity ---------------------------------------------------

    @staticmethod
    def _tokens(text: str | None) -> set[str]:
        words = {w for w in re.findall(r"\b[a-z0-9]{3,}\b", (text or "").lower())}
        return words - _STOPWORDS

    def _reduce_topic(self, candidate: ProcessedCandidate) -> tuple[float, str | None]:
        """Return (max similarity, matched recent topic) for the candidate title."""
        cand_tokens = self._tokens(candidate.topic_suggestion or candidate.clean_title)
        if not cand_tokens:
            return 0.0, None
        best_sim = 0.0
        best_topic: str | None = None
        for job in self._history:
            job_tokens = self._tokens(job.topic)
            if not job_tokens:
                continue
            inter = len(cand_tokens & job_tokens)
            union = len(cand_tokens | job_tokens)
            sim = inter / union if union else 0.0
            if sim > best_sim:
                best_sim = sim
                best_topic = job.topic
        return best_sim, best_topic

    # -- category fatigue ----------------------------------------------------

    def _classify(self, candidate: ProcessedCandidate):
        """Determine the strategy that would be generated for this candidate."""
        if self._strategist is None:
            from strategy.topic_strategist import TopicStrategist

            self._strategist = TopicStrategist(self.config)
        try:
            return self._strategist.develop_strategy(candidate)
        except Exception as exc:
            logger.warning("DiversityScorer could not develop strategy: %s", exc)
            return None

    @staticmethod
    def _job_categories(job: JobRecord) -> dict[str, str]:
        strat = {}
        try:
            raw = json.loads(job.strategy_json or "{}")
            strat = raw if isinstance(raw, dict) else {}
        except Exception:
            pass
        return {
            "content_format": job.content_format or strat.get("content_format") or "explainer",
            "hook_strategy": job.hook_strategy or strat.get("hook_strategy") or "curiosity_gap",
            "target_audience": job.target_audience or strat.get("target_audience") or "general_consumers",
            "topic_pattern": PerformanceInsightsEngine.classify_topic_pattern(job.topic),
        }

    def _fatigued_dimensions(self, candidate_categories: dict[str, str]) -> list[str]:
        """Dimensions whose category repeats `fatigue_threshold`+ times in the window."""
        counts: dict[str, int] = {}
        for job in self._history:
            hist = self._job_categories(job)
            for dim, cat in candidate_categories.items():
                if hist.get(dim) == cat:
                    counts[dim] = counts.get(dim, 0) + 1
        return [dim for dim, n in counts.items() if n >= self.fatigue_threshold]

    # -- public interface ---------------------------------------------------

    def explain(self, candidate: ProcessedCandidate) -> tuple[float, list[str]]:
        """Return (additive delta, reasons). Delta is <= 0 (or 0 when no fatigue)."""
        total = 0.0
        reasons: list[str] = []

        sim, matched = self._reduce_topic(candidate)
        if matched and sim >= self.topic_sim_threshold:
            total += self.topic_sim_penalty
            preview = matched if len(matched) <= 90 else matched[:87] + "..."
            reasons.append(
                f"Diversity: topic near-duplicate of recent job {preview!r} "
                f"(similarity {sim:.2f} >= {self.topic_sim_threshold:.2f})"
            )

        strategy = self._classify(candidate)
        if strategy is not None:
            cand_cats = {
                "content_format": strategy.content_format.value,
                "hook_strategy": strategy.hook_strategy.value,
                "target_audience": strategy.target_audience.value,
                "topic_pattern": PerformanceInsightsEngine.classify_topic_pattern(
                    strategy.topic
                ),
            }
            fatigued = self._fatigued_dimensions(cand_cats)
            if fatigued:
                total += self.fatigue_penalty
                labels = {
                    "content_format": "format",
                    "hook_strategy": "hook",
                    "target_audience": "audience",
                    "topic_pattern": "topic pattern",
                }
                reasons.append(
                    "Diversity: strategy categories overused in recent window ("
                    + ", ".join(labels[d] for d in fatigued)
                    + f", >= {self.fatigue_threshold} of last {len(self._history)} jobs)"
                )

        total = min(total, self.max_total_penalty)
        delta = -round(total, 1)
        return delta, reasons

    def score(self, candidate: ProcessedCandidate) -> float:
        """Bounded additive score: raw score minus any diversity penalties."""
        delta, _ = self.explain(candidate)
        if delta == 0.0:
            return candidate.score
        return round(min(100.0, max(0.0, candidate.score + delta)), 1)

    def rerank(
        self, candidates: Sequence[ProcessedCandidate]
    ) -> list[tuple[ProcessedCandidate, float, list[str]]]:
        scored = [(c, self.score(c), self.explain(c)[1]) for c in candidates]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored