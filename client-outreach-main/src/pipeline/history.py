"""Job history and duplicate-generation tracking store."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from processors.deduplicator import canonicalize_url

logger = logging.getLogger(__name__)


class HistoryRecord(BaseModel):
    """Record of a successfully generated video from a candidate or topic."""

    candidate_id: str | None = None
    topic: str
    slug: str
    source_name: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    score: float = 0.0
    status: str = "ok"
    video_path: str | None = None
    audio_path: str | None = None
    script_path: str | None = None
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HistoryStore:
    """Manages the history.json ledger to prevent duplicate video generation."""

    def __init__(self, history_file: Path | str) -> None:
        self.path = Path(history_file)
        self.records: list[HistoryRecord] = []
        self._seen_ids: set[str] = set()
        self._seen_urls: set[str] = set()
        self._seen_topics: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            items = raw.get("records", []) if isinstance(raw, dict) else raw
            self.records = [HistoryRecord(**it) for it in items]
            for rec in self.records:
                if rec.candidate_id:
                    self._seen_ids.add(rec.candidate_id)
                if rec.source_url:
                    self._seen_urls.add(canonicalize_url(rec.source_url))
                if rec.topic:
                    self._seen_topics.add(rec.topic.strip().lower())
        except Exception as exc:
            logger.warning("Failed to parse history from %s: %s", self.path, exc)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_records": len(self.records),
            "records": [rec.model_dump(mode="json") for rec in self.records],
        }
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def is_already_generated(self, candidate_id: str | None = None, url: str | None = None, topic: str | None = None) -> bool:
        """Check if a candidate ID, URL, or topic was already generated."""
        if candidate_id and candidate_id in self._seen_ids:
            return True
        if url and canonicalize_url(url) in self._seen_urls:
            return True
        if topic and topic.strip().lower() in self._seen_topics:
            return True
        return False

    def record(self, record: HistoryRecord) -> None:
        """Add and persist a new generation record."""
        self.records.append(record)
        if record.candidate_id:
            self._seen_ids.add(record.candidate_id)
        if record.source_url:
            self._seen_urls.add(canonicalize_url(record.source_url))
        if record.topic:
            self._seen_topics.add(record.topic.strip().lower())
        self.save()