"""Tests for AnalyticsCollector simulation and live endpoints."""

from analytics.collector import AnalyticsCollector
from db.database import Database
from db.models import JobRecord, JobStatus, PublishStatus


def test_analytics_collector_generates_snapshot_for_job(tmp_path):
    db = Database(tmp_path / "test.db")
    collector = AnalyticsCollector(db=db)

    job = JobRecord(
        id="job_collect_1",
        slug="collector-test",
        topic="Testing Collector",
        status=JobStatus.STAGED,
        publish_status=PublishStatus.STAGED,
        published_platform="youtube",
        quality_score=95.0,
    )
    db.save_job(job)

    snaps = collector.fetch_job_metrics(job, dry_run=True)
    assert len(snaps) == 1
    assert snaps[0].metrics.views > 0
    assert snaps[0].metrics.retention_rate_pct > 0

    # Ensure saved to DB
    in_db = db.list_snapshots(job_id=job.id)
    assert len(in_db) == 1


def test_analytics_collector_sync_all_jobs(tmp_path):
    db = Database(tmp_path / "test.db")
    collector = AnalyticsCollector(db=db)

    j1 = JobRecord(
        id="job_sync_1",
        slug="sync-1",
        topic="Job 1",
        status=JobStatus.PUBLISHED,
        published_platform="all",
    )
    j2 = JobRecord(
        id="job_sync_2",
        slug="sync-2",
        topic="Job 2",
        status=JobStatus.PENDING_REVIEW,  # Not eligible
    )
    db.save_job(j1)
    db.save_job(j2)

    snaps = collector.sync_all_jobs(dry_run=True)
    # j1 has published_platform='all' -> yields 2 snapshots (youtube + instagram)
    assert len(snaps) == 2