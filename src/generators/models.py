"""Structured multi-scene script data model with visual and B-roll requirements."""

from __future__ import annotations

import json
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator

SegmentKind = Literal["hook", "main", "cta"]

# Approximate speaking rate for word budgeting (words per minute). Edge-TTS
# neural voices typically speak ~150 wpm at default rate.
WORDS_PER_MINUTE = 150


class Scene(BaseModel):
    """A visual scene in a short video with narration, visual requirements, and B-roll cues."""

    scene_index: int = 1
    kind: str = "main"  # "hook" | "setup" | "point" | "payoff" | "cta"
    narration: str = ""
    visual_description: str = ""
    broll_keywords: list[str] = Field(default_factory=list)
    transition: str = "fade"
    estimated_duration: float = 0.0


class ScriptSegment(BaseModel):
    """One segment/scene of a short-form script."""

    kind: SegmentKind
    text: str
    visual_prompt: str = ""
    broll_keywords: list[str] = Field(default_factory=list)
    tone: str = "engaging"
    transition: str = "fade"

    @field_validator("text")
    @classmethod
    def text_must_be_nonempty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("script segment text cannot be empty")
        return text


class ShortScript(BaseModel):
    """A structured 30–50 second short-form video script with multi-scene support.

    Deliberately structured instead of free-floating prose so downstream
    engines (voice, subtitles, B-roll compositor) can rely on stable fields.
    """

    topic: str
    title: str = Field(default="")
    segments: list[ScriptSegment] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    target_seconds: int = 40
    provider: str = "unknown"
    provenance: dict[str, Any] = Field(default_factory=dict)
    strategy: dict[str, Any] = Field(default_factory=dict)

    @property
    def hook(self) -> ScriptSegment | None:
        return next((s for s in self.segments if s.kind == "hook"), None)

    @property
    def main(self) -> ScriptSegment | None:
        return next((s for s in self.segments if s.kind == "main"), None)

    @property
    def cta(self) -> ScriptSegment | None:
        return next((s for s in self.segments if s.kind == "cta"), None)

    @property
    def full_text(self) -> str:
        """The spoken narration, segments joined by paragraph breaks."""
        return "\n\n".join(s.text for s in self.segments)

    @property
    def word_count(self) -> int:
        return sum(len(s.text.split()) for s in self.segments)

    @property
    def estimated_seconds(self) -> float:
        """Rough speech duration based on a standard speaking rate."""
        return self.word_count / WORDS_PER_MINUTE * 60

    @property
    def all_scenes(self) -> list[Scene]:
        """Return explicit scenes or construct them automatically from segments."""
        if self.scenes:
            return self.scenes
        constructed: list[Scene] = []
        for idx, seg in enumerate(self.segments, start=1):
            w_count = len(seg.text.split())
            est_sec = w_count / WORDS_PER_MINUTE * 60
            constructed.append(
                Scene(
                    scene_index=idx,
                    kind=seg.kind,
                    narration=seg.text,
                    visual_description=seg.visual_prompt or f"Scene {idx} representing {seg.kind}",
                    broll_keywords=seg.broll_keywords,
                    transition=seg.transition,
                    estimated_duration=est_sec,
                )
            )
        return constructed

    def validate_timing(self, max_seconds: int = 50) -> list[str]:
        """Return a list of timing warnings (empty when on target)."""
        warnings: list[str] = []
        est = self.estimated_seconds
        if est > max_seconds:
            warnings.append(
                f"script estimated at {est:.0f}s, over the {max_seconds}s target; "
                "trim content or speak faster"
            )
        for segment in self.segments:
            if not segment.text:
                warnings.append(f"empty {segment.kind} segment")
        return warnings

    def model_dump_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            indent=2,
            ensure_ascii=False,
        )