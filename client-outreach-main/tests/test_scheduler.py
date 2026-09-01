"""Tests for ScheduledPipeline worker."""

import json
from pathlib import Path
from db.database import Database
from db.models import JobStatus
from processors.models import ProcessedCandidate, ProcessingBatch
from scheduler import ScheduledPipeline


def test_scheduled_pipeline_run_cycle_with_existing_candidates(tmp_path):
    db = Database(tmp_path / "test.db")
    proc_dir = tmp_path / "processed"
    proc_dir.mkdir(parents=True)

    cand = ProcessedCandidate(
        id="cand_sched_1",
        source_name="TechFeed",
        source_url="https://techfeed.com/article",
        raw_title="AI Automation in 2026",
        clean_title="AI Automation in 2026",
        topic_suggestion="AI Automation in 2026",
        summary="Automating routine tasks using AI and code scripts.",
        clean_body="Step by step guide to build automation pipelines.",
        score=70.0,
    )
    batch = ProcessingBatch(total_input=1, total_valid=1, candidates=[cand])
    (proc_dir / "latest.json").write_text(batch.model_dump_json(), encoding="utf-8")

    config = {
        "pipeline": {"output_dir": str(tmp_path)},
        "script": {"target_seconds": 40},
    }

    sched = ScheduledPipeline(config=config, db=db)
    jobs = sched.run_cycle(limit=1, min_score=30.0, skip_collect=True, render_video=False)

    assert len(jobs) == 1
    assert jobs[0].candidate_id == "cand_sched_1"
    assert jobs[0].status == JobStatus.PENDING_REVIEW

    # Check database persistence
    db_job = db.get_job("job_ai-automation-in-2026")
    assert db_job is not None
    assert db_job.status == JobStatus.PENDING_REVIEW