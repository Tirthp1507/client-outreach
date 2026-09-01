"""TTS engine interface.

Keep engines interchangeable: the pipeline only depends on this interface, so
Switching ``edge_tts`` for ElevenLabs later means adding a new engine class and
a config value — not touching the rest of the code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from voice.models import VoiceResult


class TTSEngineError(Exception):
    """Raised when a TTS engine fails to synthesise or write audio."""


class TTSEngine(ABC):
    name: str = "abstract"

    @abstractmethod
    def synthesize(self, text: str, output_path: str, **kwargs) -> VoiceResult:
        """Synthesise ``text`` to ``output_path`` and return timings.

        ``output_path`` may include any extension the engine supports; the
        engine must write the correct container for it.
        """

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"{type(self).__name__}(name={self.name!r})"