"""Abstract base class for content collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from collectors.models import RawContentItem


class CollectorError(Exception):
    """Raised when content collection fails unexpectedly."""


class BaseCollector(ABC):
    """Base interface for all content collectors (RSS, Reddit, YouTube, APIs)."""

    def __init__(self, name: str, config: dict[str, Any] | None = None) -> None:
        self.name = name
        self.config = config or {}

    @abstractmethod
    def collect(self, limit: int = 20) -> list[RawContentItem]:
        """Fetch content items from the configured source(s)."""
        raise NotImplementedError