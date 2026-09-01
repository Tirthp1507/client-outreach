"""Crash recovery and state synchronization for interrupted pipeline jobs."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import get_config
from db.database import Database
from db.models import JobRecord, JobStatus, PublishStatus
from pipeline.quality import QualityValidator

logger = logging.getLogger(__name__)


class JobRecoveryEngine:
    """Detects and repairs stale in-flight jobs after unexpected shutdowns or crashes."""

    def __init__(self, db: Database | None = None, config: dict[str, Any] | None = None) -> None:
        self.db = db or Database()
        self.config = config or get_config()
        self.qa_validator = QualityValidator()

    def recover_stale_jobs(self) -> list[JobRecord]:
        """Find and safely recover jobs stuck in transient GENERATING or PUBLISHING states."""
        all_jobs = self.db.list_jobs(limit=200)
        recovered: list[JobRecord] = []

        for job in all_jobs:
            if job.status in (JobStatus.GENERATING, JobStatus.QA):
                logger.warning("Found interrupted generation job: %s (%s)", job.id, job.status)
                # Check if video was rendered before crash
                if job.video_path and Path(job.video_path).exists() and Path(job.video_path).stat().st_size > 50_000:
                    job.status = JobStatus.PENDING_REVIEW
                    job.notes = "Automatically recovered from interrupted generation (artifacts verified)"
                    logger.info("Recovered job %s to PENDING_REVIEW", job.id)
                else:
                    job.status = JobStatus.FAILED
                    job.notes = "Generation interrupted by process exit; ready for retry"
                    logger.info("Marked incomplete job %s as FAILED", job.id)

                self.db.save_job(job)
                recovered.append(job)

            elif job.status == JobStatus.PUBLISHING or job.publish_status == PublishStatus.PUBLISHING:
                logger.warning("Found interrupted publishing job: %s", job.id)
                job.status = JobStatus.FAILED
                job.publish_status = PublishStatus.FAILED
                job.last_publish_error = "Publishing interrupted by process shutdown; safe to retry"
                self.db.save_job(job)
                recovered.append(job)

        return recovered

    def reset_failed_job_for_retry(self, job_id: str) -> JobRecord | None:
        """Reset a FAILED job back to PENDING_REVIEW or APPROVED so it can be re-evaluated or re-published."""
        job = self.db.get_job(job_id)
        if not job:
            return None

        job.status = JobStatus.APPROVED if job.quality_passed else JobStatus.PENDING_REVIEW
        job.publish_status = PublishStatus.NOT_STARTED
        job.last_publish_error = None
        job.notes = f"Manually reset for retry on {datetime.now(timezone.utc).isoformat()}"
        return self.db.save_job(job)