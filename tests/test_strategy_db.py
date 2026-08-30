"""Tests for SQLite database persistence of strategy decisions."""

from db.database import Database
from db.models import JobRecord, JobStatus


def test_database_persists_strategy_fields(tmp_path):
    db_file = tmp_path / "strat_test.db"
    db = Database(db_file)

    job = JobRecord(
        id="job_strat_1",
        slug="ai-breakthrough",
        topic="AI Breakthrough",
        content_format="news",
        hook_strategy="statistic_shock",
        target_audience="general_consumers",
        strategy_json='{"recommended_angle": "The real cost of AI"}',
        status=JobStatus.PENDING_REVIEW,
        score=85.0,
        quality_score=95.0,
    )

    db.save_job(job)

    fetched = db.get_job("job_strat_1")
    assert fetched is not None
    assert fetched.content_format == "news"
    assert fetched.hook_strategy == "statistic_shock"
    assert fetched.target_audience == "general_consumers"
    assert fetched.parsed_strategy["recommended_angle"] == "The real cost of AI"