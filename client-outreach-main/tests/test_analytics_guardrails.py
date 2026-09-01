"""Tests for Phase 10 strict statistical guardrails in the insights/feedback engine."""

import json

from analytics.insights import PerformanceInsightsEngine
from analytics.models import PerformanceSnapshot, PlatformMetrics
from db.database import Database
from db.models import JobRecord, JobStatus


def _snapshot(db: Database, job_id: str, snap_id: str, *, engagement: float, views: int = 1000) -> None:
    db.save_snapshot(
        PerformanceSnapshot(
            id=snap_id,
            job_id=job_id,
            slug=job_id,
            platform="youtube",
            metrics=PlatformMetrics(views=views, likes=int(views * 0.08), retention_rate_pct=80.0),
            engagement_score=engagement,
        )
    )


def _news_job(db: Database, job_id: str) -> None:
    db.save_job(
        JobRecord(
            id=job_id, slug=job_id, topic="Regulators probe record settlement deal",
            status=JobStatus.PUBLISHED, content_format="news",
            hook_strategy="statistic_shock", target_audience="general_consumers",
            strategy_json=json.dumps({"scene_count": 4, "target_duration_seconds": 40, "cta_strategy": "save"}),
        )
    )


def _list_job(db: Database, job_id: str) -> None:
    db.save_job(
        JobRecord(
            id=job_id, slug=job_id, topic="Top 5 productivity tools for developers",
            status=JobStatus.PUBLISHED, content_format="list",
            hook_strategy="curiosity_gap", target_audience="tech_enthusiasts",
            strategy_json=json.dumps({"scene_count": 3, "target_duration_seconds": 35, "cta_strategy": "save"}),
        )
    )


def test_single_hot_job_cannot_manufacture_signal(tmp_path):
    """4 snapshots of ONE job must NOT produce a multiplier (distinct-job guard)."""
    db = Database(tmp_path / "guard.db")
    _news_job(db, "hot_job")
    for i in range(4):
        _snapshot(db, "hot_job", f"s_hot_{i}", engagement=90.0)
    # A low-performing second job brings the global benchmark down, so the news
    # category would look 'above average' if snapshots alone were trusted.
    _list_job(db, "cold_job")
    _snapshot(db, "cold_job", "s_cold", engagement=10.0)

    engine = PerformanceInsightsEngine(db=db, config={"analytics": {"min_samples": 3, "min_jobs": 2}})

    mults = engine.get_feedback_multipliers(min_samples=3, min_jobs=2)
    assert mults["content_format"]["news"] == 1.0  # distinct jobs = 1 -> neutral

    boost, reasons = engine.best_feedback_boost(
        {"content_format": "news"}, min_samples=3, min_jobs=2
    )
    assert boost == 0.0
    assert not reasons

    report = engine.generate_insights(min_samples=3, min_jobs=2)
    news_findings = [
        f for f in report.findings
        if f.dimension == "content_format" and f.category == "news"
    ]
    assert news_findings[0].reliable is False


def test_effect_size_floor_keeps_noise_neutral(tmp_path):
    """Categories within min_effect of the benchmark stay neutral (no noise nudges)."""
    db = Database(tmp_path / "effect.db")
    _news_job(db, "n1"); _news_job(db, "n2")
    _list_job(db, "l1"); _list_job(db, "l2")
    # news avg 74 vs benchmark 70.5 -> ratio 1.0496, effect 0.0496 < 0.10.
    _snapshot(db, "n1", "n1a", engagement=74.0)
    _snapshot(db, "n2", "n2a", engagement=74.0)
    _snapshot(db, "l1", "l1a", engagement=67.0)
    _snapshot(db, "l2", "l2a", engagement=67.0)

    engine = PerformanceInsightsEngine(db=db, config={"analytics": {"min_effect": 0.10, "min_samples": 2}})
    mults = engine.get_feedback_multipliers(min_samples=2, min_jobs=2, min_effect=0.10)
    assert mults["content_format"]["news"] == 1.0  # effect below floor

    # Control: a clear effect is NOT blocked by the guardrail.
    strong = Database(tmp_path / "strong.db")
    _news_job(strong, "n1"); _news_job(strong, "n2")
    _list_job(strong, "l1"); _list_job(strong, "l2")
    _snapshot(strong, "n1", "n1a", engagement=90.0)
    _snapshot(strong, "n2", "n2a", engagement=90.0)
    _snapshot(strong, "l1", "l1a", engagement=50.0)
    _snapshot(strong, "l2", "l2a", engagement=50.0)
    strong_mults = PerformanceInsightsEngine(
        db=strong, config={"analytics": {"min_effect": 0.10, "min_samples": 2}}
    ).get_feedback_multipliers(min_samples=2, min_jobs=2, min_effect=0.10)
    assert strong_mults["content_format"]["news"] != 1.0  # clear signal passes


def test_combined_feedback_boost_bounded_and_capped(tmp_path):
    from tests.test_analytics_feedback import _populate_balanced

    db = Database(tmp_path / "combined.db")
    _populate_balanced(db)
    engine = PerformanceInsightsEngine(db=db, config={"analytics": {"min_samples": 2}})

    categories = {
        "content_format": "news",
        "hook_strategy": "statistic_shock",
        "target_audience": "general_consumers",
        "topic_pattern": "news",
        "scene_count": "4_scenes",
        "target_duration": "40_49s",
    }
    boost, reasons = engine.combined_feedback_boost(categories, min_samples=2, max_points=10.0)
    # Multiple correlated dimensions -> summed, then hard-capped at max_points.
    assert boost == 10.0
    assert reasons

    # No reliable category -> strict no-op, exactly like best mode.
    none_boost, none_reasons = engine.combined_feedback_boost(
        {"content_format": "news"}, min_samples=10
    )
    assert none_boost == 0.0
    assert none_reasons == []


def test_quality_band_dimension(tmp_path):
    from tests.test_analytics_feedback import _populate_balanced

    db = Database(tmp_path / "qband.db")
    _populate_balanced(db)
    engine = PerformanceInsightsEngine(db=db)

    assert PerformanceInsightsEngine.bucket_quality(0.0) == "0_69"
    assert PerformanceInsightsEngine.bucket_quality(86.4) == "80_89"
    assert PerformanceInsightsEngine.bucket_quality(98.0) == "90_plus"

    report = engine.generate_insights(min_samples=2)
    assert "quality_band" in report.dimensions
    qb = [f for f in report.findings if f.dimension == "quality_band"]
    assert qb and {f.category for f in qb} == {"0_69"}