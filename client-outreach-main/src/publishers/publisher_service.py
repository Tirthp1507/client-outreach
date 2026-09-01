"""Publishing service enforcing approval gates, duplicate prevention, and retry backoff."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from config import get_config
from db.database import Database
from db.models import JobRecord, JobStatus, PublishStatus
from pipeline.safeguards import PublishQuotaGuard
from publishers.base import BasePublisher, PublishResult
from publishers.instagram_publisher import InstagramPublisher
from publishers.youtube_publisher import YouTubePublisher

logger = logging.getLogger(__name__)


class PublishingGateError(Exception):
    """Raised when a job fails the approval gate or duplicate prevention check."""


class PublisherService:
    """Orchestrates production publishing with approval enforcement, retries, and persistence."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        db: Database | None = None,
        *,
        live: bool = False,
    ) -> None:
        self.config = config or get_config()
        self.db = db or Database()
        self.live = live
        self.quota_guard = PublishQuotaGuard(db=self.db, config=self.config)
        self.publishers: dict[str, BasePublisher] = {
            "youtube": YouTubePublisher(self.config, live=self.live),
            "instagram": InstagramPublisher(self.config, live=self.live),
        }


    def validate_approval_gate(self, job: JobRecord, platform: str, *, force: bool = False) -> None:
        """Enforce approval state and duplicate publishing prevention."""
        if job.status == JobStatus.REJECTED:
            raise PublishingGateError(
                f"Job {job.id} was REJECTED by reviewer and cannot be published."
            )

        if job.status == JobStatus.PENDING_REVIEW:
            raise PublishingGateError(
                f"Job {job.id} is PENDING_REVIEW. It must be APPROVED before publishing."
            )

        if job.status not in (JobStatus.APPROVED, JobStatus.STAGED, JobStatus.PUBLISHING, JobStatus.FAILED):
            raise PublishingGateError(
                f"Job {job.id} is in status={job.status.value!r}. Only APPROVED/STAGED jobs may be published."
            )

        # Duplicate publishing check
        if job.publish_status == PublishStatus.PUBLISHED and not force:
            raise PublishingGateError(
                f"Job {job.id} has already been PUBLISHED to {job.published_platform or 'platforms'} "
                f"(Post ID: {job.platform_post_id}, URL: {job.platform_url}). Use force=True to republish."
            )

    def publish_job(
        self,
        job_id_or_slug: str,
        platform: str = "all",
        *,
        dry_run: bool = False,
        force: bool = False,
        max_retries: int = 3,
    ) -> dict[str, PublishResult]:
        """Publish an approved job with safety checks and retry backoff."""
        job = self.db.get_job(job_id_or_slug)
        if not job:
            raise ValueError(f"Job not found in database: {job_id_or_slug}")

        target_platforms = ["youtube", "instagram"] if platform.lower() == "all" else [platform.lower()]
        for p in target_platforms:
            if p not in self.publishers:
                raise ValueError(f"Unsupported publishing platform: {p!r}. Choose from {list(self.publishers.keys())} or 'all'")

        # 1. Enforce Approval Gate
        self.validate_approval_gate(job, platform, force=force)

        # 2. Update status to PUBLISHING in database
        job.status = JobStatus.PUBLISHING
        job.publish_status = PublishStatus.PUBLISHING
        self.db.save_job(job)

        results: dict[str, PublishResult] = {}
        all_passed = True

        for p_name in target_platforms:
            publisher = self.publishers[p_name]
            logger.info("Starting publish for job %s on %s (dry_run=%s)", job.id, p_name, dry_run)

            # Daily rate limit quota guard for live publishes
            if not dry_run and self.live:
                can_pub, quota_reason = self.quota_guard.can_publish(p_name)
                if not can_pub:
                    logger.warning("Publishing blocked by quota guard on %s: %s", p_name, quota_reason)
                    results[p_name] = PublishResult(
                        platform=p_name,
                        status="failed",
                        error=quota_reason,
                        message=quota_reason,
                        attempts=job.publish_attempts,
                    )
                    all_passed = False
                    continue

            res = None
            for attempt in range(1, max_retries + 1):
                job.publish_attempts += 1
                try:
                    res = publisher.publish(job, dry_run=dry_run)
                    res.attempts = job.publish_attempts
                    if res.status in ("published", "published_dry_run", "staged"):
                        break
                except Exception as exc:
                    err_str = str(exc)

                    logger.warning("Attempt %d failed on %s for job %s: %s", attempt, p_name, job.id, err_str)
                    res = PublishResult(
                        platform=p_name,
                        status="failed",
                        error=err_str,
                        message=f"Attempt {attempt} error: {err_str}",
                        attempts=job.publish_attempts,
                    )

                if attempt < max_retries:
                    backoff_delay = 0.5 * (2 ** (attempt - 1))
                    time.sleep(backoff_delay)

            results[p_name] = res
            if res.status == "failed":
                all_passed = False
                job.last_publish_error = res.error or res.message

        # 3. Update database state
        now = datetime.now(timezone.utc).isoformat()
        if all_passed:
            first_res = list(results.values())[0]
            job.status = JobStatus.PUBLISHED if (not dry_run and self.live) else JobStatus.STAGED
            job.publish_status = PublishStatus.PUBLISHED if (not dry_run and self.live) else PublishStatus.STAGED
            job.published_platform = platform
            job.platform_post_id = first_res.post_id
            job.platform_url = first_res.url
            job.published_at = now
            job.last_publish_error = None
        else:
            job.status = JobStatus.FAILED
            job.publish_status = PublishStatus.FAILED

        job.publish_response_json = json.dumps(
            {k: v.model_dump(mode="json") for k, v in results.items()},
            indent=2,
        )
        self.db.save_job(job)

        return results