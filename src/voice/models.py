"""Data models shared by TTS engines."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WordTiming(BaseModel):
    """A single spoken word with its position in the narration."""

    text: str
    start: float = Field(..., description="start time in seconds")
    end: float = Field(..., description="end time in seconds")
    sequence: int = Field(default=0, description="index in the narration")


class VoiceResult(BaseModel):
    """Outcome of a TTS synthesis call."""

    text: str
    audio_path: str
    duration_seconds: float = 0.0
    word_timings: list[WordTiming] = Field(default_factory=list)

    @property
    def end_time(self) -> float:
        if self.word_timings:
            return max(w.end for w in self.word_timings)
        return self.duration_seconds