"""Tests for AnalyticsReporter aggregation and feedback loop multipliers."""

from analytics.models import PerformanceSnapshot, PlatformMetrics
from analytics.reporter import AnalyticsReporter
from db.database import Database
from db.models import JobRecord, JobStatus


def test_analytics_reporter_groups_by_format_and_hook(tmp_path):
    db = Database(tmp_path / "test.db")
    reporter = AnalyticsReporter(db=db)

    # Job 1: News / Statistic Shock
    j1 = JobRecord(
        id="j1",
        slug="news-slug",
        topic="News Topic",
        status=JobStatus.PUBLISHED,
        content_format="news",
        hook_strategy="statistic_shock",
    )
    db.save_job(j1)
    db.save_snapshot(
        PerformanceSnapshot(
            id="s1",
            job_id="j1",
            slug="news-slug",
            platform="youtube",
            metrics=PlatformMetrics(views=5000, likes=400, retention_rate_pct=90.0),
            engagement_score=85.0,
        )
    )

    # Job 2: List / Curiosity Gap
    j2 = JobRecord(
        id="j2",
        slug="list-slug",
        topic="List Topic",
        status=JobStatus.PUBLISHED,
        content_format="list",
        hook_strategy="curiosity_gap",
    )
    db.save_job(j2)
    db.save_snapshot(
        PerformanceSnapshot(
            id="s2",
            job_id="j2",
            slug="list-slug",
            platform="youtube",
            metrics=PlatformMetrics(views=2000, likes=120, retention_rate_pct=75.0),
            engagement_score=50.0,
        )
    )

    report = reporter.generate_summary_report()
    assert report.total_views == 7000
    assert report.total_likes == 520
    assert len(report.by_format) == 2
    assert report.by_format[0].category == "news"
    assert report.by_format[0].total_views == 5000

    format_weights = reporter.get_format_performance_weights()
    assert format_weights["news"] > 1.0
    assert "list" in format_weights

    hook_weights = reporter.get_hook_performance_weights()
    assert "statistic_shock" in hook_weights