"""Tests for SQLite persistence of performance snapshots and summary columns."""

from analytics.models import PerformanceSnapshot, PlatformMetrics
from db.database import Database
from db.models import JobRecord, JobStatus, PublishStatus


def test_database_snapshot_persistence_and_job_sync(tmp_path):
    db = Database(tmp_path / "test.db")

    job = JobRecord(
        id="job_analytics_1",
        slug="analytics-test-slug",
        topic="Testing Analytics Persistence",
        status=JobStatus.PUBLISHED,
        publish_status=PublishStatus.PUBLISHED,
    )
    db.save_job(job)

    metrics = PlatformMetrics(
        views=2400,
        likes=180,
        comments=25,
        shares=15,
        retention_rate_pct=88.5,
    )
    snapshot = PerformanceSnapshot(
        id="snap_test_1",
        job_id=job.id,
        slug=job.slug,
        platform="youtube",
        metrics=metrics,
        engagement_score=metrics.engagement_score,
    )

    db.save_snapshot(snapshot)

    # Verify snapshot list
    snaps = db.list_snapshots(job_id=job.id)
    assert len(snaps) == 1
    assert snaps[0].metrics.views == 2400
    assert snaps[0].metrics.likes == 180

    # Verify latest snapshot
    latest = db.get_latest_snapshot(job.id, platform="youtube")
    assert latest is not None
    assert latest.id == "snap_test_1"

    # Verify job record was automatically updated with summary metrics
    updated_job = db.get_job(job.id)
    assert updated_job.latest_views == 2400
    assert updated_job.latest_likes == 180
    assert updated_job.latest_engagement_score > 0
    assert updated_job.metrics_updated_at is not None