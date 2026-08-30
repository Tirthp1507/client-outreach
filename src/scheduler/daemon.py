"""Long-running continuous automation daemon with graceful signal handling and operational audit logging."""

from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from analytics.collector import AnalyticsCollector
from config import PROJECT_ROOT, get_config
from db.database import Database
from db.models import AuditLogRecord
from pipeline.recovery import JobRecoveryEngine
from pipeline.safeguards import PublishQuotaGuard, StoragePruningEngine, SystemHealthMonitor
from scheduler.runner import ScheduledPipeline

logger = logging.getLogger(__name__)


class AutomationDaemon:
    """Continuous production daemon executing collection, rendering, metrics sync, and maintenance."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        db: Database | None = None,
        *,
        interval_minutes: int = 60,
        batch_limit: int = 1,
        min_score: float = 30.0,
        prune_days: int = 7,
        dry_run: bool = False,
    ) -> None:
        self.config = config or get_config()
        self.db = db or Database()
        self.interval_minutes = interval_minutes
        self.batch_limit = batch_limit
        self.min_score = min_score
        self.prune_days = prune_days
        self.dry_run = dry_run

        self._running = False
        self._shutdown_requested = False

        self.scheduled_pipeline = ScheduledPipeline(self.config, db=self.db)
        self.recovery_engine = JobRecoveryEngine(db=self.db, config=self.config)
        self.analytics_collector = AnalyticsCollector(db=self.db, config=self.config)
        self.pruning_engine = StoragePruningEngine()
        self.health_monitor = SystemHealthMonitor(db=self.db)

        # Setup graceful signal handlers
        self._setup_signals()

    def _setup_signals(self) -> None:
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except Exception:
            pass  # Some environments or non-main threads might not support signal registration

    def _handle_signal(self, signum: int, frame: Any) -> None:
        logger.info("Received termination signal (%s). Initiating graceful daemon shutdown...", signum)
        self._shutdown_requested = True
        self._running = False

    def execute_single_cycle(self, cycle_type: str = "daemon_cycle") -> AuditLogRecord:
        """Execute one complete scheduled maintenance and generation cycle with audit tracking."""
        start_dt = datetime.now(timezone.utc)
        started_at = start_dt.isoformat()
        cycle_id = f"audit_{cycle_type}_{int(start_dt.timestamp())}"

        items_collected = 0
        candidates_processed = 0
        jobs_generated = 0
        qa_passed = 0
        qa_failed = 0
        published_count = 0
        errors_count = 0
        details: dict[str, Any] = {}

        logger.info("--- Starting Automation Cycle [%s] ---", cycle_id)

        # 1. Recovery Check: Clean up any stale in-flight jobs
        try:
            recovered = self.recovery_engine.recover_stale_jobs()
            if recovered:
                details["recovered_jobs"] = [j.id for j in recovered]
                logger.info("Daemon: Recovered %d stale jobs", len(recovered))
        except Exception as exc:
            errors_count += 1
            logger.warning("Daemon: Recovery check failed: %s", exc)

        # 2. Automated Pipeline Cycle
        try:
            created_jobs = self.scheduled_pipeline.run_cycle(
                limit=self.batch_limit,
                min_score=self.min_score,
                render_video=True,
            )
            jobs_generated = len(created_jobs)
            for j in created_jobs:
                if j.quality_passed:
                    qa_passed += 1
                else:
                    qa_failed += 1
            details["created_job_ids"] = [j.id for j in created_jobs]
        except Exception as exc:
            errors_count += 1
            details["pipeline_error"] = str(exc)
            logger.error("Daemon: Pipeline execution error: %s", exc)

        # 3. Analytics Synchronization
        try:
            snapshots = self.analytics_collector.sync_all_jobs(dry_run=self.dry_run)
            details["synced_snapshots_count"] = len(snapshots)
        except Exception as exc:
            errors_count += 1
            logger.warning("Daemon: Analytics sync failed: %s", exc)

        # 4. Storage Retention Pruning
        try:
            prune_res = self.pruning_engine.prune_artifacts(
                older_than_days=self.prune_days,
                dry_run=self.dry_run,
            )
            details["pruning"] = prune_res
        except Exception as exc:
            logger.warning("Daemon: Storage pruning failed: %s", exc)

        # 5. Health Check
        health = self.health_monitor.check_health()
        details["health_status"] = health.get("status")

        end_dt = datetime.now(timezone.utc)
        completed_at = end_dt.isoformat()
        duration_sec = round((end_dt - start_dt).total_seconds(), 2)

        cycle_status = "success"
        if errors_count > 0:
            cycle_status = "partial" if jobs_generated > 0 else "failed"

        audit_record = AuditLogRecord(
            id=cycle_id,
            cycle_type=cycle_type,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration_sec,
            items_collected=items_collected,
            candidates_processed=candidates_processed,
            jobs_generated=jobs_generated,
            qa_passed_count=qa_passed,
            qa_failed_count=qa_failed,
            published_count=published_count,
            errors_count=errors_count,
            status=cycle_status,
            details_json=str(details),
        )

        self.db.save_audit_log(audit_record)
        logger.info("--- Cycle Complete [%s] Status: %s Duration: %.2fs ---", cycle_id, cycle_status, duration_sec)
        return audit_record

    def run_forever(self) -> None:
        """Run continuous daemon loop until interrupted."""
        self._running = True
        logger.info(
            "Automation Daemon active. Cycle interval: %d min, Batch size: %d, Min score: %.1f",
            self.interval_minutes,
            self.batch_limit,
            self.min_score,
        )

        while self._running and not self._shutdown_requested:
            try:
                self.execute_single_cycle(cycle_type="daemon_cycle")
            except Exception as exc:
                logger.critical("Unexpected daemon cycle crash: %s", exc)

            if not self._running or self._shutdown_requested:
                break

            # Sleep in 1-second slices so shutdown signals respond immediately
            sleep_seconds = self.interval_minutes * 60
            logger.info("Daemon sleeping for %d seconds...", sleep_seconds)
            for _ in range(sleep_seconds):
                if not self._running or self._shutdown_requested:
                    break
                time.sleep(1)

        logger.info("Automation Daemon stopped gracefully.")