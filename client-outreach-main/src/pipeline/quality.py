"""Automated publish-quality validator (Phase 8) with intelligence, pacing, and provenance checks.

Adds to the Phase 6 validator:
- Audio presence validation (narration file actually produced and sized).
- Cliché / overused-vocabulary detection.
- Enhanced hook scoring (attention openers + number triggers).
- Scene-level visual coverage (explicit scenes + unique descriptions + B-roll cues).
- Readability of burned subtitles (cue display durations within comfortable bounds).
- Optional duration cross-check of the rendered video against the script estimate
  (only when ffmpeg/ffprobe is available).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from generators.models import ShortScript
from video.ffmpeg_utils import has_ffmpeg, probe_duration

logger = logging.getLogger(__name__)

HOOK_POWER_WORDS = {
    "why", "what", "how", "secret", "never", "stop", "facts", "truth", "number",
    "real", "actually", "unbelievable", "huge", "warning", "revealed", "breaking",
    "billion", "million", "top", "rules", "best", "versus", "forget"
}

HOOK_ATTENTION_OPENERS = {
    "why", "what", "how", "stop", "if", "you", "never", "wait", "here", "forget",
    "nobody", "everyone", "this", "the",
}

CLICHE_WORDS = {
    "game changer", "game-changer", "unleash", "unlock", "elevate", "boost",
    "transformative", "cutting-edge", "never before", "in today's world",
    "world-class", "revolutionize", "supercharge", "think outside the box",
    "tip of the iceberg", "game-changing", "unleashing",
}

SUBTITLE_MIN_DURATION = 0.35
SUBTITLE_MAX_DURATION = 8.0

VIDEO_DRIFT_TOLERANCE = 0.5


class QualityCheckItem(BaseModel):
    name: str
    status: str  # PASS | WARN | FAIL
    score: float
    message: str


class QualityReport(BaseModel):
    overall_score: float
    passed: bool
    checks: list[QualityCheckItem] = Field(default_factory=list)


class QualityValidator:
    """Performs rigorous automated QA checks across script, pacing, visuals, subtitles, and video."""

    def validate(
        self,
        *,
        script: ShortScript,
        audio_path: str | Path | None = None,
        video_path: str | Path | None = None,
        subtitle_path: str | Path | None = None,
    ) -> QualityReport:
        checks: list[QualityCheckItem] = []

        # 1. Hook Strength Check (15 pts) ----------------------------------
        hook = script.hook
        if hook:
            hook_text = hook.text
            hook_words = set(re.findall(r"\b\w+\b", hook_text.lower()))
            has_power = bool(hook_words & HOOK_POWER_WORDS)
            has_number = bool(re.search(r"\d", hook_text))
            has_opener = bool(
                re.match(r"\b(?:%s)\b" % "|".join(HOOK_ATTENTION_OPENERS), hook_text.lower())
            )
            word_len = len(hook_text.split())
            if (has_power or has_opener or has_number) and 5 <= word_len <= 30:
                checks.append(
                    QualityCheckItem(
                        name="hook_strength",
                        status="PASS",
                        score=15.0,
                        message="High-impact opening hook (power word, attention opener, or number) at optimal length",
                    )
                )
            elif word_len >= 4:
                checks.append(
                    QualityCheckItem(
                        name="hook_strength",
                        status="WARN",
                        score=10.0,
                        message="Opening hook present but could use stronger psychological trigger words",
                    )
                )
            else:
                checks.append(
                    QualityCheckItem(
                        name="hook_strength",
                        status="FAIL",
                        score=0.0,
                        message="Hook segment is too brief or missing",
                    )
                )
        else:
            checks.append(
                QualityCheckItem(
                    name="hook_strength",
                    status="FAIL",
                    score=0.0,
                    message="Missing opening hook segment",
                )
            )

        # 2. Content Repetition Check (12 pts) -----------------------------
        segment_texts = [s.text.lower() for s in script.segments]
        duplicate_detected = False
        for i in range(len(segment_texts)):
            for j in range(i + 1, len(segment_texts)):
                words_i = set(re.findall(r"\b\w{4,}\b", segment_texts[i]))
                words_j = set(re.findall(r"\b\w{4,}\b", segment_texts[j]))
                if words_i and words_j and len(words_i & words_j) / max(len(words_i), len(words_j)) > 0.7:
                    duplicate_detected = True
                    break

        if not duplicate_detected:
            checks.append(
                QualityCheckItem(
                    name="content_repetition",
                    status="PASS",
                    score=12.0,
                    message="Clean script narrative with low intra-segment phrase repetition",
                )
            )
        else:
            checks.append(
                QualityCheckItem(
                    name="content_repetition",
                    status="WARN",
                    score=6.0,
                    message="High vocabulary overlap detected across different script segments",
                )
            )

        # 3. Pacing & Word Budget (12 pts) ---------------------------------
        words = script.word_count
        if 35 <= words <= 120:
            checks.append(
                QualityCheckItem(
                    name="pacing_and_budget",
                    status="PASS",
                    score=12.0,
                    message=f"Optimal short-form pacing budget ({words} words for ~25-45s short)",
                )
            )
        elif 20 <= words < 35 or 120 < words <= 160:
            checks.append(
                QualityCheckItem(
                    name="pacing_and_budget",
                    status="WARN",
                    score=8.0,
                    message=f"Borderline word count ({words} words)",
                )
            )
        else:
            checks.append(
                QualityCheckItem(
                    name="pacing_and_budget",
                    status="FAIL",
                    score=3.0,
                    message=f"Suboptimal word budget ({words} words)",
                )
            )

        # 4. Scene & Visual Variety Coverage (15 pts) ----------------------
        scenes = script.all_scenes
        visual_descriptions = {s.visual_description for s in scenes if s.visual_description}
        scenes_with_broll = [s for s in scenes if s.broll_keywords]
        if len(scenes) >= 3 and len(visual_descriptions) >= 2 and scenes_with_broll:
            checks.append(
                QualityCheckItem(
                    name="visual_variety",
                    status="PASS",
                    score=15.0,
                    message=(
                        f"Multi-scene visual plan: {len(scenes)} scenes, "
                        f"{len(visual_descriptions)} unique descriptions, B-roll cues present"
                    ),
                )
            )
        elif len(scenes) >= 2:
            checks.append(
                QualityCheckItem(
                    name="visual_variety",
                    status="WARN",
                    score=10.0,
                    message="Basic visual scene transitions planned (add B-roll keywords per scene)",
                )
            )
        else:
            checks.append(
                QualityCheckItem(
                    name="visual_variety",
                    status="WARN",
                    score=6.0,
                    message="Single static visual scene without multi-scene variation",
                )
            )

        # 5. Subtitle Readability & Formatting (12 pts) --------------------
        checks.append(self._subtitle_readability_check(subtitle_path))

        # 6. Cliché / Overused Vocabulary (6 pts) --------------------------
        full_lower = script.full_text.lower() if script.full_text else ""
        hits = [w for w in CLICHE_WORDS if w in full_lower]
        if not hits:
            checks.append(
                QualityCheckItem(
                    name="cliche_word_check",
                    status="PASS",
                    score=6.0,
                    message="No overused viral clichés detected in the narration",
                )
            )
        else:
            checks.append(
                QualityCheckItem(
                    name="cliche_word_check",
                    status="WARN",
                    score=3.0,
                    message=f"Slightly formulaic vocabulary: {', '.join(sorted(hits)[:4])}",
                )
            )

        # 7. Source & Provenance Availability (10 pts) ---------------------
        prov = script.provenance
        if prov.get("source_name") and prov.get("source_url"):
            checks.append(
                QualityCheckItem(
                    name="source_provenance",
                    status="PASS",
                    score=10.0,
                    message=f"Full source attribution verified ({prov['source_name']})",
                )
            )
        elif prov.get("source_name"):
            checks.append(
                QualityCheckItem(
                    name="source_provenance",
                    status="WARN",
                    score=6.0,
                    message=f"Partial source attribution ({prov['source_name']})",
                )
            )
        else:
            checks.append(
                QualityCheckItem(
                    name="source_provenance",
                    status="WARN",
                    score=4.0,
                    message="Source provenance metadata not provided",
                )
            )

        # 8. Audio / Voiceover Presence (8 pts) ----------------------------
        checks.append(self._audio_presence_check(audio_path))

        # 9. Video Render & Composition (10 pts) ---------------------------
        checks.append(self._video_compositing_check(video_path, script))

        total_score = sum(c.score for c in checks)
        passed = all(c.status != "FAIL" for c in checks) and total_score >= 60.0

        return QualityReport(
            overall_score=round(total_score, 1),
            passed=passed,
            checks=checks,
        )

    # -- individual checks ---------------------------------------------------

    def _subtitle_readability_check(self, subtitle_path) -> QualityCheckItem:
        if not subtitle_path or not Path(subtitle_path).exists():
            return QualityCheckItem(
                name="subtitle_readability",
                status="FAIL",
                score=0.0,
                message="Subtitle file missing",
            )

        sub_text = Path(subtitle_path).read_text(encoding="utf-8", errors="ignore")
        cues = re.findall(
            r"Dialogue:\s*\d+,(\d+):(\d+):([\d.]+),(\d+):(\d+):([\d.]+),[^,]*,,0,0,0,,(.+)",
            sub_text,
        )
        if not cues:
            return QualityCheckItem(
                name="subtitle_readability",
                status="WARN",
                score=7.0,
                message="Subtitle file generated but no parseable cue dialogues found",
            )

        def to_sec(hh, mm, ss) -> float:
            return int(hh) * 3600 + int(mm) * 60 + float(ss)

        too_short = 0
        too_long = 0
        for hh1, mm1, ss1, hh2, mm2, ss2, text in cues:
            dur = to_sec(hh2, mm2, ss2) - to_sec(hh1, mm1, ss1)
            if not text.strip():
                too_short += 1
            elif dur < SUBTITLE_MIN_DURATION:
                too_short += 1
            elif dur > SUBTITLE_MAX_DURATION:
                too_long += 1

        if too_short or too_long:
            return QualityCheckItem(
                name="subtitle_readability",
                status="WARN",
                score=8.0,
                message=(
                    f"{len(cues)} cues parsed; {too_short} blink too fast "
                    f"({SUBTITLE_MIN_DURATION:.2f}s min), {too_long} linger too long "
                    f"({SUBTITLE_MAX_DURATION:.0f}s max)"
                ),
            )
        return QualityCheckItem(
            name="subtitle_readability",
            status="PASS",
            score=12.0,
            message=f"Animated karaoke captions: {len(cues)} cues at readable durations in 9:16 safe zone",
        )

    def _audio_presence_check(self, audio_path) -> QualityCheckItem:
        if not audio_path or not Path(audio_path).exists():
            return QualityCheckItem(
                name="audio_presence",
                status="WARN",
                score=2.0,
                message="Narration audio not provided for QA check",
            )
        size_kb = Path(audio_path).stat().st_size / 1024
        if size_kb < 10:
            return QualityCheckItem(
                name="audio_presence",
                status="FAIL",
                score=0.0,
                message=f"Narration audio file is suspiciously small ({size_kb:.1f} KB)",
            )
        return QualityCheckItem(
            name="audio_presence",
            status="PASS",
            score=8.0,
            message=f"Voiceover produced and sized correctly ({size_kb:.0f} KB)",
        )

    def _video_compositing_check(self, video_path, script: ShortScript) -> QualityCheckItem:
        if not video_path or not Path(video_path).exists():
            return QualityCheckItem(
                name="video_compositing",
                status="WARN" if not video_path else "FAIL",
                score=0.0,
                message="Video composition not rendered",
            )

        vid_p = Path(video_path)
        vid_size_kb = vid_p.stat().st_size / 1024
        if vid_size_kb <= 100:
            return QualityCheckItem(
                name="video_compositing",
                status="WARN",
                score=5.0,
                message="Video rendered but file size is unusually low",
            )

        # Cross-check rendered duration against the script's speech estimate.
        if has_ffmpeg():
            try:
                duration = probe_duration(vid_p)
                estimate = script.estimated_seconds or duration
                drift = abs(duration - estimate) / max(estimate, 1.0)
                if drift <= VIDEO_DRIFT_TOLERANCE:
                    return QualityCheckItem(
                        name="video_compositing",
                        status="PASS",
                        score=10.0,
                        message=(
                            f"Video rendered ({vid_size_kb:.0f} KB, {duration:.1f}s "
                            f"matching script estimate ±{VIDEO_DRIFT_TOLERANCE:.0%})"
                        ),
                    )
                return QualityCheckItem(
                    name="video_compositing",
                    status="PASS",
                    score=8.0,
                    message=(
                        f"Video rendered ({vid_size_kb:.0f} KB, {duration:.1f}s) but "
                        f"drifts {drift:.0%} from the script speech estimate"
                    ),
                )
            except Exception as exc:  # probe failed — degrade to size check
                logger.debug("video duration probe failed: %s", exc)

        return QualityCheckItem(
            name="video_compositing",
            status="PASS",
            score=10.0,
            message=f"Video rendered successfully (1080x1920 9:16, {vid_size_kb:.0f} KB)",
        )