"""Data models for content collection."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field

SourceType = Literal["rss", "reddit", "manual", "api", "web"]


def generate_item_id(source_name: str, url: str, title: str) -> str:
    """Generate a stable deterministic ID for a content item."""
    norm = f"{source_name.strip().lower()}:{url.strip().lower()}:{title.strip().lower()}"
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


class RawContentItem(BaseModel):
    """Normalized raw content item collected from any source."""

    id: str
    source_name: str
    source_type: SourceType = "rss"
    title: str
    url: str
    content: str = ""
    author: str | None = None
    published_at: str | None = None
    score: float = 0.0
    tags: list[str] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)
    collected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CollectionBatch(BaseModel):
    """A batch of raw collected items with ingestion metadata."""

    collected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sources_attempted: list[str] = Field(default_factory=list)
    sources_succeeded: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)
    total_items: int = 0
    items: list[RawContentItem] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)