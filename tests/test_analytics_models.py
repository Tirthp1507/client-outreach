"""Tests for Phase 9 analytics data models and composite score formulas."""

from analytics.models import PlatformMetrics, PerformanceSnapshot, AnalyticsSummaryReport, FormatPerformance


def test_platform_metrics_engagement_rate_and_score():
    m = PlatformMetrics(
        views=1000,
        likes=80,
        comments=10,
        shares=10,
        retention_rate_pct=85.0,
    )
    # (80 + 10 + 10) / 1000 = 10%
    assert m.engagement_rate == 10.0
    # base = min(50, 1000/100) = 10
    # retention = min(30, 85 * 0.3) = 25.5
    # interaction = min(20, 10 * 2.0) = 20.0
    # total = 10 + 25.5 + 20 = 55.5
    assert m.engagement_score == 55.5


def test_performance_snapshot_defaults():
    snap = PerformanceSnapshot(
        id="snap_123",
        job_id="job_test",
        slug="test-short",
        platform="youtube",
        metrics=PlatformMetrics(views=500, likes=30),
    )
    assert snap.platform == "youtube"
    assert snap.metrics.views == 500