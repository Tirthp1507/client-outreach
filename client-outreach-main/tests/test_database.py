"""Tests for SQLite database storage and job lifecycle tracking."""

from db.database import Database
from db.models import JobRecord, JobStatus


def test_database_init_and_job_lifecycle(tmp_path):
    db_file = tmp_path / "test.db"
    db = Database(db_file)

    job = JobRecord(
        id="job_productivity_1",
        slug="top-3-productivity-hacks",
        topic="Top 3 Productivity Hacks",
        source_name="Manual",
        status=JobStatus.PENDING_REVIEW,
        score=85.0,
        quality_score=95.0,
        youtube_title="Top 3 Productivity Hacks #Shorts",
        instagram_caption="⚡ Top 3 Productivity Hacks",
    )

    db.save_job(job)

    # Read back
    fetched = db.get_job("job_productivity_1")
    assert fetched is not None
    assert fetched.slug == "top-3-productivity-hacks"
    assert fetched.status == JobStatus.PENDING_REVIEW
    assert fetched.quality_score == 95.0

    # Update status to APPROVED
    updated = db.update_status("job_productivity_1", JobStatus.APPROVED, notes="Approved by editor")
    assert updated is not None
    assert updated.status == JobStatus.APPROVED
    assert updated.notes == "Approved by editor"

    # Update metadata
    edited = db.update_metadata("job_productivity_1", youtube_title="New Viral Title #Shorts")
    assert edited is not None
    assert edited.youtube_title == "New Viral Title #Shorts"

    # List jobs
    jobs = db.list_jobs(status=JobStatus.APPROVED)
    assert len(jobs) == 1
    assert jobs[0].id == "job_productivity_1"