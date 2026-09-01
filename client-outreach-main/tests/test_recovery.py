"""Tests for JobRecoveryEngine crash recovery and health restoration."""

from db.database import Database
from db.models import JobRecord, JobStatus, PublishStatus
from pipeline.recovery import JobRecoveryEngine


def test_recovery_engine_recovers_completed_generating_job(tmp_path):
    db = Database(tmp_path / "test.db")
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"0" * 100_000)

    job = JobRecord(
        id="job_gen_done",
        slug="gen-done",
        topic="Interrupted But Finished Video",
        status=JobStatus.GENERATING,
        video_path=str(vid_file),
    )
    db.save_job(job)

    engine = JobRecoveryEngine(db=db)
    recovered = engine.recover_stale_jobs()

    assert len(recovered) == 1
    updated = db.get_job("job_gen_done")
    assert updated.status == JobStatus.PENDING_REVIEW
    assert "Automatically recovered" in updated.notes


def test_recovery_engine_marks_incomplete_generating_job_as_failed(tmp_path):
    db = Database(tmp_path / "test.db")

    job = JobRecord(
        id="job_gen_stalled",
        slug="gen-stalled",
        topic="Stalled Incomplete Job",
        status=JobStatus.GENERATING,
        video_path=None,
    )
    db.save_job(job)

    engine = JobRecoveryEngine(db=db)
    recovered = engine.recover_stale_jobs()

    assert len(recovered) == 1
    updated = db.get_job("job_gen_stalled")
    assert updated.status == JobStatus.FAILED
    assert "interrupted" in updated.notes


def test_recovery_engine_recovers_stuck_publishing_job(tmp_path):
    db = Database(tmp_path / "test.db")

    job = JobRecord(
        id="job_pub_stuck",
        slug="pub-stuck",
        topic="Stuck Publishing Job",
        status=JobStatus.PUBLISHING,
        publish_status=PublishStatus.PUBLISHING,
    )
    db.save_job(job)

    engine = JobRecoveryEngine(db=db)
    recovered = engine.recover_stale_jobs()

    assert len(recovered) == 1
    updated = db.get_job("job_pub_stuck")
    assert updated.status == JobStatus.FAILED
    assert updated.publish_status == PublishStatus.FAILED


def test_recovery_engine_resets_failed_job_for_retry(tmp_path):
    db = Database(tmp_path / "test.db")

    job = JobRecord(
        id="job_failed_1",
        slug="failed-slug",
        topic="Failed Job Ready For Retry",
        status=JobStatus.FAILED,
        publish_status=PublishStatus.FAILED,
        last_publish_error="Network timeout",
        quality_passed=True,
    )
    db.save_job(job)

    engine = JobRecoveryEngine(db=db)
    reset_job = engine.reset_failed_job_for_retry("job_failed_1")

    assert reset_job is not None
    assert reset_job.status == JobStatus.APPROVED
    assert reset_job.publish_status == PublishStatus.NOT_STARTED
    assert reset_job.last_publish_error is None