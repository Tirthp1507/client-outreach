"""Tests for Phase 10 operational safeguards, rate limiting, and health monitoring."""

import os
import time
from datetime import datetime, timezone
from db.database import Database
from db.models import JobRecord, JobStatus, PublishStatus
from pipeline.safeguards import PublishQuotaGuard, StoragePruningEngine, SystemHealthMonitor
from publishers.publisher_service import PublisherService



def test_publish_quota_guard_daily_limits(tmp_path):
    db = Database(tmp_path / "test.db")
    guard = PublishQuotaGuard(db=db)

    # Initially 0 published today -> allowed
    allowed, reason = guard.can_publish("youtube")
    assert allowed is True
    assert "Within daily quota" in reason

    # Save 5 published jobs for today
    today = datetime.now(timezone.utc).isoformat()
    for i in range(5):
        job = JobRecord(
            id=f"job_pub_{i}",
            slug=f"job-pub-{i}",
            topic=f"Topic {i}",
            status=JobStatus.PUBLISHED,
            publish_status=PublishStatus.PUBLISHED,
            published_platform="youtube",
            published_at=today,
        )
        db.save_job(job)

    # Now daily limit (5) is reached -> blocked
    allowed, reason = guard.can_publish("youtube")
    assert allowed is False
    assert "Daily publish quota exceeded" in reason

    # Instagram still allowed (0 used)
    allowed_ig, _ = guard.can_publish("instagram")
    assert allowed_ig is True


def test_publisher_service_blocks_when_quota_exceeded(tmp_path):
    db = Database(tmp_path / "test.db")
    today = datetime.now(timezone.utc).isoformat()
    # Saturate quota
    for i in range(5):
        db.save_job(JobRecord(
            id=f"sat_{i}",
            slug=f"sat-{i}",
            topic=f"Topic {i}",
            status=JobStatus.PUBLISHED,
            publish_status=PublishStatus.PUBLISHED,
            published_platform="youtube",
            published_at=today,
        ))

    approved_job = JobRecord(
        id="approved_candidate",
        slug="approved-cand",
        topic="Ready for publish",
        status=JobStatus.APPROVED,
    )
    db.save_job(approved_job)

    # In live mode (dry_run=False, live=True), PublisherService should block youtube
    service = PublisherService(db=db, live=True)
    results = service.publish_job(approved_job.id, platform="youtube", dry_run=False)
    assert results["youtube"].status == "failed"
    assert "Daily publish quota exceeded" in results["youtube"].error


def test_storage_pruning_engine(tmp_path):
    output_dir = tmp_path / "output"
    drafts_dir = output_dir / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)

    test_file = drafts_dir / "old_subtitle.ass"
    test_file.write_text("dummy", encoding="utf-8")
    # Set mtime to 10 days ago
    old_time = time.time() - (10 * 86400)
    os.utime(test_file, (old_time, old_time))

    engine = StoragePruningEngine(output_dir=output_dir)

    # Pruning with 7 days should identify the 10-day-old file
    res = engine.prune_artifacts(older_than_days=7, dry_run=True)
    assert res["deleted_count"] >= 1
    assert test_file.exists()  # dry_run kept file

    res_real = engine.prune_artifacts(older_than_days=7, dry_run=False)
    assert res_real["deleted_count"] >= 1
    assert not test_file.exists()



def test_system_health_monitor(tmp_path):
    db = Database(tmp_path / "test.db")
    monitor = SystemHealthMonitor(db=db, output_dir=tmp_path)

    health = monitor.check_health()
    assert health["status"] in ("healthy", "degraded")
    assert "disk_free_gb" in health
    assert "jobs_summary" in health
    assert "quota_status" in health