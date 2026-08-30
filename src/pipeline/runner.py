"""Pipeline runner — orchestrates Topic/Candidate -> Script -> Voice -> Video -> Quality -> Packaging."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT
from generators import ScriptProviderError, generate_script, generate_script_from_candidate
from pipeline.quality import QualityReport, QualityValidator
from processors.models import ProcessedCandidate
from publishers import MetadataGenerator, PlatformMetadataPackage
from utils import slugify
from video import FFmpegCompositor, MissingFFmpegError, VideoCompositorError
from voice import EdgeTTSEngine, TTSEngineError
from voice.subtitle_aligner import (
    DEFAULT_MAX_LINE_CHARS,
    DEFAULT_MAX_LINES,
    build_captions,
    scene_regions_from_timings,
    write_subtitle_files,
)

logger = logging.getLogger(__name__)

__all__ = ["PipelineResult", "PipelineRunner"]


class PipelineStepError(Exception):
    """A required pipeline stage failed."""


@dataclass
class PipelineResult:
    topic: str
    slug: str
    script: Any = None
    candidate_id: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    timing_warnings: list[str] = field(default_factory=list)
    quality_score: float = 0.0
    quality_report: QualityReport | None = None
    platform_metadata: PlatformMetadataPackage | None = None
    strategy: dict[str, Any] = field(default_factory=dict)
    blocked: list[str] = field(default_factory=list)
    status: str = "ok"

    def summary(self) -> str:
        lines = [
            f"Pipeline finished with status='{self.status}' (Quality: {self.quality_score:.1f}/100) for topic={self.topic!r}"
        ]
        for name, path in self.artifacts.items():
            lines.append(f"  - {name}: {path}")
        for warn in self.timing_warnings:
            lines.append(f"  ! {warn}")
        for blk in self.blocked:
            lines.append(f"  x blocked: {blk}")
        return "\n".join(lines)


class PipelineRunner:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.root = Path(
            (self.config.get("pipeline", {}) or {}).get("output_dir", "output") or "output"
        )
        if not self.root.is_absolute():
            self.root = PROJECT_ROOT / self.root
        self.quality_validator = QualityValidator()
        self.metadata_generator = MetadataGenerator()

    # -- path helpers ------------------------------------------------------

    def _job_dir(self, slug: str) -> dict[str, Path]:
        return {
            "scripts": self.root / "scripts",
            "audio": self.root / "audio",
            "drafts": self.root / "drafts",
            "final": self.root / "final",
        }

    def run_candidate(
        self,
        candidate: ProcessedCandidate,
        *,
        provider: str | None = None,
        voice: str | None = None,
        render_video: bool = True,
        seed: int | None = None,
    ) -> PipelineResult:
        """Run the end-to-end pipeline using a ProcessedCandidate."""
        topic = candidate.topic_suggestion.strip()
        slug = slugify(topic or candidate.clean_title)
        dirs = self._job_dir(slug)
        for directory in dirs.values():
            directory.mkdir(parents=True, exist_ok=True)

        result = PipelineResult(
            topic=topic,
            slug=slug,
            candidate_id=candidate.id,
            provenance={
                "candidate_id": candidate.id,
                "source_name": candidate.source_name,
                "source_url": candidate.source_url,
                "source_title": candidate.raw_title,
                "clean_title": candidate.clean_title,
                "score": candidate.score,
                "score_reasons": candidate.reasons,
            },
        )
        self.config = self._with_runtime_overrides(provider=provider, voice=voice)

        # 1) Script from candidate -----------------------------------------
        try:
            script = generate_script_from_candidate(
                candidate, self.config, provider=provider, seed=seed
            )
        except ScriptProviderError as exc:
            raise PipelineStepError(f"script generation failed: {exc}") from exc

        return self._execute_downstream(
            script=script,
            result=result,
            slug=slug,
            dirs=dirs,
            voice=voice,
            render_video=render_video,
        )

    def run(
        self,
        topic: str,
        *,
        provider: str | None = None,
        voice: str | None = None,
        render_video: bool = True,
        seed: int | None = None,
    ) -> PipelineResult:
        """Run the end-to-end pipeline from a raw topic string."""
        topic = topic.strip()
        if not topic:
            raise ValueError("topic is required")
        slug = slugify(topic)
        dirs = self._job_dir(slug)
        for directory in dirs.values():
            directory.mkdir(parents=True, exist_ok=True)

        result = PipelineResult(topic=topic, slug=slug)
        self.config = self._with_runtime_overrides(provider=provider, voice=voice)

        # 1) Script from topic ---------------------------------------------
        try:
            script = generate_script(
                topic, self.config, provider=provider, seed=seed
            )
        except ScriptProviderError as exc:
            raise PipelineStepError(f"script generation failed: {exc}") from exc

        return self._execute_downstream(
            script=script,
            result=result,
            slug=slug,
            dirs=dirs,
            voice=voice,
            render_video=render_video,
        )

    def _execute_downstream(
        self,
        script: Any,
        result: PipelineResult,
        slug: str,
        dirs: dict[str, Path],
        voice: str | None,
        render_video: bool,
    ) -> PipelineResult:
        result.script = script
        result.timing_warnings = script.validate_timing(
            max_seconds=int((self.config.get("script", {}) or {}).get("max_seconds", 50))
        )

        script_path = dirs["scripts"] / f"{slug}.json"
        script_path.write_text(script.model_dump_json(), encoding="utf-8")
        result.artifacts["script"] = str(script_path)

        # 2) Voice ---------------------------------------------------------
        try:
            engine = EdgeTTSEngine(
                voice=voice
                or (self.config.get("voice", {}) or {}).get("voice", "en-US-JennyNeural"),
                rate=(self.config.get("voice", {}) or {}).get("rate", "+0%"),
                pitch=(self.config.get("voice", {}) or {}).get("pitch", "+0Hz"),
                volume=(self.config.get("voice", {}) or {}).get("volume", "+0%"),
            )
            voice_result = engine.synthesize(
                script.full_text,
                str(dirs["audio"] / f"{slug}.mp3"),
            )
        except TTSEngineError as exc:
            raise PipelineStepError(f"voice generation failed: {exc}") from exc

        result.artifacts["audio"] = voice_result.audio_path
        result.artifacts["word_timings"] = str(dirs["drafts"] / f"{slug}.timings.json")
        _write_timings(voice_result.word_timings, result.artifacts["word_timings"])

        # 3) Captions (Animated Pop / Highlight) ----------------------------
        # Scene-aware: captions align to scene boundaries and get per-kind styling;
        # a scene-header track labels each section on-screen.
        scene_regions = scene_regions_from_timings(voice_result.word_timings, script.all_scenes)
        captions = build_captions(
            voice_result.word_timings,
            max_line_chars=int(
                (self.config.get("video", {}) or {}).get(
                    "subtitle_max_line_chars", DEFAULT_MAX_LINE_CHARS
                )
            ),
            max_lines=int(
                (self.config.get("video", {}) or {}).get(
                    "subtitle_max_lines", DEFAULT_MAX_LINES
                )
            ),
            scene_regions=scene_regions or None,
        )
        sub_paths = write_subtitle_files(
            captions,
            dirs["drafts"] / slug,
            width=int((self.config.get("video", {}) or {}).get("width", 1080)),
            height=int((self.config.get("video", {}) or {}).get("height", 1920)),
            font_size=int((self.config.get("video", {}) or {}).get("subtitle_font_size", 68)),
            animated_highlight=True,
            scene_regions=scene_regions or None,
            write_headers=True,
        )
        result.artifacts.update(
            {
                "subtitles_srt": sub_paths["srt"],
                "subtitles_ass": sub_paths["ass"],
                "scene_headers": sub_paths.get("headers", ""),
            }
        )

        # 4) Video ---------------------------------------------------------
        if render_video:
            try:
                compositor = FFmpegCompositor(self.config)
                video_summary = compositor.compose(
                    voice_path=voice_result.audio_path,
                    subtitle_path=sub_paths["ass"],
                    header_path=sub_paths.get("headers"),
                    output_path=str(dirs["final"] / f"{slug}.mp4"),
                    scenes=script.all_scenes,
                    content_format=(script.strategy or {}).get("content_format", "default"),
                    total_duration=float(voice_result.duration_seconds),
                )
                result.artifacts["video"] = video_summary["output_path"]
            except MissingFFmpegError as exc:
                result.status = "partial"
                result.blocked.append(str(exc))
            except VideoCompositorError as exc:
                result.status = "partial"
                result.blocked.append(f"video composition failed: {exc}")

        # 5) Quality QA Validation ----------------------------------------
        q_report = self.quality_validator.validate(
            script=script,
            audio_path=result.artifacts.get("audio"),
            video_path=result.artifacts.get("video"),
            subtitle_path=result.artifacts.get("subtitles_ass"),
        )
        result.quality_report = q_report
        result.quality_score = q_report.overall_score

        # 6) Platform Metadata & Thumbnail Packaging ----------------------
        platform_pkg = self.metadata_generator.generate(
            script=script,
            slug=slug,
            video_path=result.artifacts.get("video"),
            output_dir=dirs["final"],
        )
        result.platform_metadata = platform_pkg
        if platform_pkg.thumbnail_path:
            result.artifacts["thumbnail"] = platform_pkg.thumbnail_path

        # Save platform packaging file
        publish_file = dirs["final"] / f"{slug}.publish.json"
        publish_file.write_text(platform_pkg.model_dump_json(indent=2), encoding="utf-8")
        result.artifacts["publish_metadata"] = str(publish_file)

        # 7) Provenance & Metadata Artifact -------------------------------
        result.strategy = getattr(script, "strategy", {}) or {}
        meta_payload = {
            "topic": result.topic,
            "slug": result.slug,
            "candidate_id": result.candidate_id,
            "provenance": result.provenance,
            "strategy": result.strategy,
            "quality_score": result.quality_score,
            "quality_passed": q_report.passed,
            "quality_checks": [c.model_dump(mode="json") for c in q_report.checks],
            "status": result.status,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifacts": result.artifacts,
            "youtube": platform_pkg.youtube.model_dump(mode="json"),
            "instagram": platform_pkg.instagram.model_dump(mode="json"),
        }
        meta_path = dirs["final"] / f"{slug}.meta.json"
        meta_path.write_text(json.dumps(meta_payload, indent=2, ensure_ascii=False), encoding="utf-8")
        result.artifacts["metadata"] = str(meta_path)

        return result

    # -- internal ----------------------------------------------------------

    def _with_runtime_overrides(
        self, *, provider: str | None, voice: str | None
    ) -> dict[str, Any]:
        cfg = self.config
        if provider:
            cfg = {**cfg, "pipeline": {**(cfg.get("pipeline") or {}), "script_provider": provider}}
        if voice:
            cfg = {**cfg, "voice": {**(cfg.get("voice") or {}), "voice": voice}}
        return cfg


def _write_timings(timings, path: str) -> None:
    payload = [t.model_dump(mode="json") for t in timings]
    Path(path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )