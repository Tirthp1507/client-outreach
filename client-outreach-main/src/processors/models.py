"""Data models for content processing and candidate ranking."""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ProcessedCandidate(BaseModel):
    """A clean, scored, and summarized content candidate ready for script generation."""

    id: str
    source_name: str
    source_url: str
    raw_title: str
    clean_title: str
    topic_suggestion: str
    summary: str
    clean_body: str
    score: float = 0.0
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    word_count: int = 0
    processed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProcessingBatch(BaseModel):
    """Results from processing a collection batch."""

    processed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_input: int = 0
    total_valid: int = 0
    total_duplicates_removed: int = 0
    candidates: list[ProcessedCandidate] = Field(default_factory=list)