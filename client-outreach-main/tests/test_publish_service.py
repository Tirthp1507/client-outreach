"""Tests for PublisherService: approval gates, duplicate publishing prevention, and retry backoff."""

import pytest
from db.database import Database
from db.models import JobRecord, JobStatus, PublishStatus
from publishers.publisher_service import PublisherService, PublishingGateError


def test_publisher_service_rejects_pending_review(tmp_path):
    db = Database(tmp_path / "test.db")
    job = JobRecord(
        id="job_pending_1",
        slug="pending-slug",
        topic="Pending Topic",
        status=JobStatus.PENDING_REVIEW,
        video_path=str(tmp_path / "video.mp4"),
    )
    (tmp_path / "video.mp4").write_bytes(b"0" * 100_000)
    db.save_job(job)

    service = PublisherService(db=db, live=False)
    with pytest.raises(PublishingGateError, match="must be APPROVED"):
        service.publish_job("job_pending_1", platform="youtube", dry_run=True)


def test_publisher_service_rejects_rejected_jobs(tmp_path):
    db = Database(tmp_path / "test.db")
    job = JobRecord(
        id="job_rejected_1",
        slug="rejected-slug",
        topic="Rejected Topic",
        status=JobStatus.REJECTED,
        video_path=str(tmp_path / "video.mp4"),
    )
    (tmp_path / "video.mp4").write_bytes(b"0" * 100_000)
    db.save_job(job)

    service = PublisherService(db=db, live=False)
    with pytest.raises(PublishingGateError, match="was REJECTED"):
        service.publish_job("job_rejected_1", platform="all", dry_run=True)


def test_publisher_service_prevents_duplicate_publishing(tmp_path):
    db = Database(tmp_path / "test.db")
    job = JobRecord(
        id="job_dup_1",
        slug="dup-slug",
        topic="Dup Topic",
        status=JobStatus.APPROVED,
        publish_status=PublishStatus.PUBLISHED,
        platform_post_id="yt_12345",
        platform_url="https://youtube.com/shorts/yt_12345",
        video_path=str(tmp_path / "video.mp4"),
    )
    (tmp_path / "video.mp4").write_bytes(b"0" * 100_000)
    db.save_job(job)

    service = PublisherService(db=db, live=False)
    with pytest.raises(PublishingGateError, match="already been PUBLISHED"):
        service.publish_job("job_dup_1", platform="youtube", dry_run=True, force=False)

    # With force=True, publishing proceeds
    results = service.publish_job("job_dup_1", platform="youtube", dry_run=True, force=True)
    assert "youtube" in results
    assert results["youtube"].status == "published_dry_run"


def test_publisher_service_dry_run_success_for_approved_job(tmp_path):
    db = Database(tmp_path / "test.db")
    job = JobRecord(
        id="job_app_1",
        slug="app-slug",
        topic="Approved Topic",
        status=JobStatus.APPROVED,
        youtube_title="Approved Topic #Shorts",
        instagram_caption="Approved Topic caption",
        video_path=str(tmp_path / "video.mp4"),
    )
    (tmp_path / "video.mp4").write_bytes(b"0" * 100_000)
    db.save_job(job)

    service = PublisherService(db=db, live=False)
    results = service.publish_job("job_app_1", platform="all", dry_run=True)

    assert "youtube" in results
    assert "instagram" in results
    assert results["youtube"].status == "published_dry_run"
    assert results["instagram"].status == "published_dry_run"

    # Verify database state
    updated_job = db.get_job("job_app_1")
    assert updated_job.publish_status == PublishStatus.STAGED
    assert updated_job.publish_attempts >= 1