"""Selection-scorer factory: combines diversity + performance feedback scoring.

The single integration point a selection step (CLI ``auto`` or a scheduler
cycle) can call to obtain one composite scorer object exposing
``score(candidate)`` / ``explain(candidate)`` / ``has_signal``. Both
constituent scorers are additive and opt-in via configuration; the factory
returns ``None`` when neither is enabled or when neither has any signal, so
the existing raw-score ranking is preserved exactly.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from config import PROJECT_ROOT, get_config
from processors.models import ProcessedCandidate

if TYPE_CHECKING:
    from db.database import Database

logger = logging.getLogger(__name__)



class SelectionScorer:
    """Composite additive scorer (diversity penalties + performance feedback)."""

    def __init__(self, scorers: Sequence[Any]) -> None:
        self.scorers = scorers
        self._last_breakdown: dict[str, float] = {}

    @property
    def has_signal(self) -> bool:
        return any(bool(getattr(s, "has_signal", False)) for s in self.scorers)

    def explain(self, candidate: ProcessedCandidate) -> tuple[float, list[str]]:
        total = 0.0
        reasons: list[str] = []
        self._last_breakdown = {}
        for scorer in self.scorers:
            if not getattr(scorer, "has_signal", False):
                continue
            delta, sub_reasons = scorer.explain(candidate)
            self._last_breakdown[type(scorer).__name__] = round(delta, 1)
            total += delta
            reasons.extend(sub_reasons)
        return round(total, 1), reasons

    def score(self, candidate: ProcessedCandidate) -> float:
        """Bounded additive score: raw score plus combined learned deltas."""
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


class SelectionLedger:
    """Append-only JSONL record of every selection decision with its rationale.

    Written under ``output/analytics/selection_ledger.jsonl`` so operators (and
    optionally Jim's observability endpoints) can audit *why* a candidate was
    (or was not) boosted without holding it in database memory.
    """

    def __init__(self, path: Path | str | None = None, config: dict[str, Any] | None = None) -> None:
        cfg = config or get_config()
        out = cfg.get("pipeline", {}).get("output_dir", "output")
        base = Path(out) if Path(out).is_absolute() else PROJECT_ROOT / out
        self.path = Path(path) if path else base / "analytics" / "selection_ledger.jsonl"

    def record(self, candidate: ProcessedCandidate, delta: float, reasons: list[str]) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "candidate_id": candidate.id,
            "title": candidate.clean_title,
            "raw_score": candidate.score,
            "adjusted_score": round(min(100.0, max(0.0, candidate.score + delta)), 1),
            "delta": round(delta, 1),
            "reasons": reasons,
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        except Exception as exc:
            logger.warning("SelectionLedger write failed: %s", exc)


def build_selection_scorer(
    db: Database | None = None,
    config: dict[str, Any] | None = None,
) -> SelectionScorer | None:
    """Build the composite selection scorer for the given configuration.

    Returns ``None`` when diversity/feedback are disabled or carry no signal,
    preserving the exact existing raw-score ranking path.
    """
    config = config or get_config()
    ana_cfg = config.get("analytics", {}) or {}
    feedback_enabled = bool(ana_cfg.get("feedback_enabled", False))
    diversity_enabled = bool(ana_cfg.get("diversity_enabled", False))

    scorers: list[Any] = []

    if feedback_enabled:
        from analytics.feedback import PerformanceFeedbackScorer

        try:
            scorer = PerformanceFeedbackScorer(db=db, config=config)
            if scorer.has_signal:
                scorers.append(scorer)
        except Exception as exc:
            logger.warning("PerformanceFeedbackScorer unavailable: %s", exc)

    if diversity_enabled:
        from analytics.diversity import DiversityScorer

        try:
            scorer = DiversityScorer(db=db, config=config)
            if scorer.has_signal:
                scorers.append(scorer)
        except Exception as exc:
            logger.warning("DiversityScorer unavailable: %s", exc)

    if not scorers:
        return None
    return SelectionScorer(scorers)