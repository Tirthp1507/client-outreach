"""Tests for Analytics CLI subcommands: analytics, analytics-summary, sync-metrics."""

from cli import build_parser, cmd_analytics, cmd_analytics_summary, cmd_intelligence, cmd_sync_metrics
from db.database import Database
from db.models import JobRecord, JobStatus


def test_cli_analytics_parser_registration():
    parser = build_parser()
    args_ana = parser.parse_args(["analytics", "--job-id", "job_123"])
    assert args_ana.command == "analytics"
    assert args_ana.job_id == "job_123"

    args_sum = parser.parse_args(["analytics-summary", "--platform", "youtube"])
    assert args_sum.command == "analytics-summary"
    assert args_sum.platform == "youtube"

    args_sync = parser.parse_args(["sync-metrics", "--dry-run"])
    assert args_sync.command == "sync-metrics"
    assert args_sync.dry_run is True

    args_intel = parser.parse_args(["intelligence", "--platform", "youtube", "--min-samples", "2"])
    assert args_intel.command == "intelligence"
    assert args_intel.platform == "youtube"
    assert args_intel.min_samples == 2

    args_div = parser.parse_args(["auto", "--diversity", "--feedback", "--limit", "2"])
    assert args_div.command == "auto"
    assert args_div.diversity is True
    assert args_div.feedback is True
    assert args_div.limit == 2


def test_cli_analytics_execution(tmp_path):
    parser = build_parser()
    db = Database(tmp_path / "automation.db")

    job = JobRecord(
        id="job_cli_ana",
        slug="cli-ana-test",
        topic="CLI Analytics Test",
        status=JobStatus.PUBLISHED,
        published_platform="youtube",
    )
    db.save_job(job)

    # 1. Sync metrics
    sync_args = parser.parse_args(["sync-metrics", "--dry-run", "--output-dir", str(tmp_path)])
    rc_sync = cmd_sync_metrics(sync_args)
    assert rc_sync == 0

    # 2. View job analytics
    ana_args = parser.parse_args(["analytics", "--job-id", job.id, "--output-dir", str(tmp_path)])
    rc_ana = cmd_analytics(ana_args)
    assert rc_ana == 0

    # 3. View summary
    sum_args = parser.parse_args(["analytics-summary", "--output-dir", str(tmp_path)])
    rc_sum = cmd_analytics_summary(sum_args)
    assert rc_sum == 0

    # 4. View intelligence insights
    intel_args = parser.parse_args(["intelligence", "--output-dir", str(tmp_path), "--min-samples", "2"])
    rc_intel = cmd_intelligence(intel_args)
    assert rc_intel == 0