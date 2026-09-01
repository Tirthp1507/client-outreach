"""Scheduled pipeline orchestration and batch execution worker."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from collectors import collect_all_sources
from config import PROJECT_ROOT, get_config
from db.database import Database
from db.models import JobRecord, JobStatus
from pipeline.history import HistoryRecord, HistoryStore
from pipeline.runner import PipelineRunner
from pipeline.selector import ContentSelector
from processors import process_content_batch

logger = logging.getLogger(__name__)


class ScheduledPipeline:
    """Orchestrates scheduled batch cycles with persistent SQLite tracking."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        db: Database | None = None,
    ) -> None:
        self.config = config or get_config()
        self.db = db or Database()
        self.history_store = HistoryStore(
            Path(self.config.get("pipeline", {}).get("output_dir", "output")) / "history.json"
        )
        self.selector = ContentSelector(self.history_store)
        self.runner = PipelineRunner(self.config)

    def run_cycle(
        self,
        *,
        limit: int = 1,
        min_score: float = 30.0,
        sources: list[str] | None = None,
        skip_collect: bool = False,
        render_video: bool = True,
    ) -> list[JobRecord]:
        """Execute one complete automated cycle and record output as PENDING_REVIEW."""
        out_base = Path(self.config.get("pipeline", {}).get("output_dir", "output"))
        if not out_base.is_absolute():
            out_base = PROJECT_ROOT / out_base

        candidates = []

        if not skip_collect:
            logger.info("Scheduler: Collecting content from %s", sources or "all sources")
            batch = collect_all_sources(self.config, sources=sources, limit=max(15, limit * 5))
            if batch.items:
                col_dir = out_base / "collected"
                col_dir.mkdir(parents=True, exist_ok=True)
                col_dir.joinpath("latest.json").write_text(batch.model_dump_json(indent=2), encoding="utf-8")

                logger.info("Scheduler: Processing %d raw items", batch.total_items)
                proc_batch = process_content_batch(batch.items, self.config)
                proc_dir = out_base / "processed"
                proc_dir.mkdir(parents=True, exist_ok=True)
                proc_dir.joinpath("latest.json").write_text(proc_batch.model_dump_json(indent=2), encoding="utf-8")
                candidates = proc_batch.candidates
        else:
            proc_latest = out_base / "processed" / "latest.json"
            if proc_latest.exists():
                try:
                    raw = json.loads(proc_latest.read_text(encoding="utf-8"))
                    from processors.models import ProcessedCandidate
                    candidates = [ProcessedCandidate(**it) for it in raw.get("candidates", [])]
                except Exception as exc:
                    logger.warning("Error reading %s: %s", proc_latest, exc)

        if not candidates:
            logger.info("Scheduler: No candidates available")
            return []

        # Optional selection scorer (Feedback / Diversity) if enabled via config
        scorer = None
        ana_cfg = self.config.get("analytics", {})
        if ana_cfg.get("feedback_enabled", False) or ana_cfg.get("diversity_enabled", False):
            try:
                from analytics.factory import build_selection_scorer
                scorer = build_selection_scorer(self.db, self.config)
            except ImportError:
                try:
                    from analytics.feedback import PerformanceFeedbackScorer
                    scorer = PerformanceFeedbackScorer(db=self.db, config=self.config)
                except Exception:
                    scorer = None

        selected = self.selector.select_candidates(
            candidates,
            limit=limit,
            min_score=min_score,
            feedback_scorer=scorer,
        )
        if not selected:
            logger.info("Scheduler: No new ungenerated candidates meeting min_score=%.1f", min_score)
            return []


        created_jobs: list[JobRecord] = []

        for cand in selected:
            logger.info("Scheduler: Generating short for %r (Score: %.1f)", cand.clean_title, cand.score)
            try:
                result = self.runner.run_candidate(cand, render_video=render_video)
            except Exception as exc:
                logger.error("Scheduler: Pipeline failed for candidate %s: %s", cand.id, exc)
                continue

            # Record in HistoryStore
            self.history_store.record(
                HistoryRecord(
                    candidate_id=cand.id,
                    topic=result.topic,
                    slug=result.slug,
                    source_name=cand.source_name,
                    source_url=cand.source_url,
                    source_title=cand.raw_title,
                    score=cand.score,
                    status=result.status,
                    video_path=result.artifacts.get("video"),
                    audio_path=result.artifacts.get("audio"),
                    script_path=result.artifacts.get("script"),
                )
            )

            # Record in SQLite Database with status PENDING_REVIEW
            yt_meta = result.platform_metadata.youtube if result.platform_metadata else None
            ig_meta = result.platform_metadata.instagram if result.platform_metadata else None

            strat_dict = result.strategy or {}
            job = JobRecord(
                id=f"job_{result.slug}",
                slug=result.slug,
                topic=result.topic,
                candidate_id=cand.id,
                source_name=cand.source_name,
                source_url=cand.source_url,
                status=JobStatus.PENDING_REVIEW,
                score=cand.score,
                quality_score=result.quality_score,
                quality_passed=result.quality_report.passed if result.quality_report else True,
                content_format=strat_dict.get("content_format", "explainer"),
                hook_strategy=strat_dict.get("hook_strategy", "curiosity_gap"),
                target_audience=strat_dict.get("target_audience", "general_consumers"),
                strategy_json=json.dumps(strat_dict) if strat_dict else "{}",
                script_json=result.script.model_dump_json() if result.script else "{}",
                youtube_title=yt_meta.title if yt_meta else "",
                youtube_description=yt_meta.description if yt_meta else "",
                youtube_tags=json.dumps(yt_meta.tags) if yt_meta else "[]",
                instagram_caption=ig_meta.caption if ig_meta else "",
                video_path=result.artifacts.get("video"),
                thumbnail_path=result.artifacts.get("thumbnail"),
                audio_path=result.artifacts.get("audio"),
            )

            self.db.save_job(job)
            created_jobs.append(job)
            logger.info("Scheduler: Saved job %s (status=PENDING_REVIEW) to SQLite", job.id)

        return created_jobs