"""Microsoft Edge text-to-speech engine (zero-cost neural voices).

Relies on the ``edge-tts`` package which talks to the free Edge / Azure
``ReadAloud`` service. Produces an audio file plus word-level timestamps that
later phases use for karaoke-style subtitles.

NOTE: this engine requires network access to Microsoft's service.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from voice.base import TTSEngine, TTSEngineError
from voice.models import VoiceResult, WordTiming

logger = logging.getLogger(__name__)

try:
    import edge_tts
except ImportError as exc:  # pragma: no cover - env dependent
    edge_tts = None  # type: ignore[assignment]
    _EDGE_IMPORT_ERROR = exc
else:
    _EDGE_IMPORT_ERROR = None

DEFAULT_VOICE = "en-US-JennyNeural"
DEFAULT_RATE = "+0%"
DEFAULT_PITCH = "+0Hz"
DEFAULT_VOLUME = "+0%"


class EdgeTTSEngine(TTSEngine):
    name = "edge_tts"

    def __init__(
        self,
        *,
        voice: str = DEFAULT_VOICE,
        rate: str = DEFAULT_RATE,
        pitch: str = DEFAULT_PITCH,
        volume: str = DEFAULT_VOLUME,
    ) -> None:
        if edge_tts is None:
            raise TTSEngineError(
                "edge-tts is not installed; pip install -r requirements.txt"
            ) from _EDGE_IMPORT_ERROR
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume

    def synthesize(self, text: str, output_path: str, **kwargs) -> VoiceResult:
        voice = kwargs.get("voice") or self.voice
        rate = kwargs.get("rate") or self.rate
        pitch = kwargs.get("pitch") or self.pitch
        volume = kwargs.get("volume") or self.volume

        if not text.strip():
            raise ValueError("text must not be empty")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        try:
            timings, duration = asyncio.run(
                self._synthesize_async(
                    text=text,
                    output_path=output,
                    voice=voice,
                    rate=rate,
                    pitch=pitch,
                    volume=volume,
                )
            )
        except Exception as exc:
            raise TTSEngineError(
                f"Edge-TTS synthesis failed (voice={voice}): {exc}"
            ) from exc

        logger.info(
            "Synthesized %s words -> %s (%.2fs) with voice=%s",
            len(timings), output, duration, voice,
        )
        return VoiceResult(
            text=text,
            audio_path=str(output),
            duration_seconds=duration,
            word_timings=timings,
        )

    @staticmethod
    async def _synthesize_async(
        *,
        text: str,
        output_path: Path,
        voice: str,
        rate: str,
        pitch: str,
        volume: str,
    ) -> tuple[list[WordTiming], float]:
        communicate = edge_tts.Communicate(
            text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
            boundary="WordBoundary",
        )

        # Write audio and collect word boundaries in one pass.
        if output_path.suffix.lower() in (".wav",):
            raise ValueError(
                "edge-tts produces MP3 only; pick an .mp3 output path"
            )

        timings: list[WordTiming] = []
        seq = 0
        with open(output_path, "wb") as fh:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio" and chunk["data"]:
                    fh.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    # Offsets are 100ns units.
                    start = chunk["offset"] / 1e7
                    end = (chunk["offset"] + chunk["duration"]) / 1e7
                    timings.append(
                        WordTiming(
                            text=chunk["text"].strip(),
                            start=round(start, 3),
                            end=round(end, 3),
                            sequence=seq,
                        )
                    )
                    seq += 1

        duration = timings[-1].end if timings else 0.0
        return timings, duration