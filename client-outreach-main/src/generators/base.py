"""Provider interface for script generation.

Implementations turn a plain topic into a :class:`ShortScript`. The concrete
provider is selected through configuration — see ``build_provider`` in
``script_generator.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from generators.models import ShortScript


class ScriptProviderError(Exception):
    """Raised when a provider fails to produce a valid script."""


class ScriptProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def generate(self, topic: str, **kwargs) -> ShortScript:
        """Produce a structured short-form script for ``topic``."""

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"{type(self).__name__}(name={self.name!r})"