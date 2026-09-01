"""Candidate selection layer with history-aware duplicate filtering."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Sequence

from pipeline.history import HistoryStore
from processors.models import ProcessedCandidate, ProcessingBatch

logger = logging.getLogger(__name__)


class ContentSelector:
    """Selects top ungenerated candidates meeting quality and score thresholds."""

    def __init__(self, history_store: HistoryStore) -> None:
        self.history = history_store

    def select_candidates(
        self,
        candidates: Sequence[ProcessedCandidate],
        *,
        limit: int = 1,
        min_score: float = 0.0,
        feedback_scorer=None,
    ) -> list[ProcessedCandidate]:
        """Filter candidates by score and generation history, returning top ranked.

        ``feedback_scorer`` (optional) is any object exposing ``score(candidate)``
        that returns an additively adjusted score. It enables Phase 9 performance
        feedback on ranking without replacing the existing score-based ordering:
        when absent or no-op, candidates sort by their raw score exactly as before.
        """
        available: list[ProcessedCandidate] = []
        for cand in candidates:
            if cand.score < min_score:
                continue
            if self.history.is_already_generated(
                candidate_id=cand.id,
                url=cand.source_url,
                topic=cand.topic_suggestion,
            ):
                logger.info("Skipping already generated candidate: %s (%s)", cand.clean_title, cand.id)
                continue
            available.append(cand)

        if feedback_scorer is not None:
            # Additive performance feedback: keeps the existing ranking fully
            # intact when the scorer has no learned signal (regular nudge <= 0).
            available.sort(key=lambda c: feedback_scorer.score(c), reverse=True)
        else:
            # Sort descending by score
            available.sort(key=lambda c: c.score, reverse=True)
        return available[:limit]

    def select_from_file(
        self,
        processed_file: Path | str,
        *,
        limit: int = 1,
        min_score: float = 0.0,
    ) -> list[ProcessedCandidate]:
        """Load processed candidates from JSON file and select top ungenerated ones."""
        path = Path(processed_file)
        if not path.exists():
            raise FileNotFoundError(f"Processed candidates file not found: {path}")

        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw.get("candidates", []) if isinstance(raw, dict) else raw
        candidates = [ProcessedCandidate(**it) for it in items]
        return self.select_candidates(candidates, limit=limit, min_score=min_score)