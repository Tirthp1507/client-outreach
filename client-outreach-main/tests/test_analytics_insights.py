"""Tests for the Phase 9 intelligence engine: correlations, insights, and feedback multipliers."""

import json

from analytics.insights import PerformanceInsightsEngine
from analytics.models import PerformanceSnapshot, PlatformMetrics
from db.database import Database
from db.models import JobRecord, JobStatus


def _add_job_snapshot(
    db: Database,
    job_id: str,
    *,
    fmt: str,
    hook: str,
    audience: str,
    scenes: int,
    duration: int,
    cta: str,
    topic: str,
    views: int,
    likes: int,
    retention: float,
    engagement: float,
) -> None:
    job = JobRecord(
        id=job_id,
        slug=job_id,
        topic=topic,
        status=JobStatus.PUBLISHED,
        content_format=fmt,
        hook_strategy=hook,
        target_audience=audience,
        strategy_json=json.dumps(
            {
                "scene_count": scenes,
                "target_duration_seconds": duration,
                "cta_strategy": cta,
            }
        ),
    )
    db.save_job(job)
    db.save_snapshot(
        PerformanceSnapshot(
            id=f"snap_{job_id}",
            job_id=job_id,
            slug=job_id,
            platform="youtube",
            metrics=PlatformMetrics(
                views=views,
                likes=likes,
                comments=5,
                shares=2,
                retention_rate_pct=retention,
            ),
            engagement_score=engagement,
        )
    )


def _populate(db: Database) -> None:
    _add_job_snapshot(
        db, "j_new1", fmt="news", hook="statistic_shock", audience="general_consumers",
        scenes=4, duration=40, cta="Save this to stay ahead and drop your take below",
        topic="Tech giants settle landmark lawsuit for 5 billion dollars",
        views=5000, likes=450, retention=90.0, engagement=90.0,
    )
    _add_job_snapshot(
        db, "j_new2", fmt="news", hook="statistic_shock", audience="general_consumers",
        scenes=4, duration=40, cta="Save this to stay ahead and drop your take below",
        topic="Regulators probe record settlement in federal court",
        views=4500, likes=330, retention=86.0, engagement=85.0,
    )
    _add_job_snapshot(
        db, "j_list1", fmt="list", hook="curiosity_gap", audience="tech_enthusiasts",
        scenes=3, duration=35, cta="Bookmark this guide for later",
        topic="Top 5 productivity tools for developers",
        views=1500, likes=80, retention=70.0, engagement=55.0,
    )
    _add_job_snapshot(
        db, "j_list2", fmt="list", hook="curiosity_gap", audience="tech_enthusiasts",
        scenes=3, duration=35, cta="Bookmark this guide for later",
        topic="Top 10 ways to speed up your workflow",
        views=1200, likes=52, retention=66.0, engagement=45.0,
    )


def test_aggregate_dimension_performance(tmp_path):
    db = Database(tmp_path / "insight.db")
    _populate(db)
    engine = PerformanceInsightsEngine(db=db)

    rows = engine.aggregate_dimension("content_format")
    assert [r.category for r in rows] == ["news", "list"]
    assert rows[0].avg_engagement_score == 87.5
    assert rows[1].avg_engagement_score == 50.0
    assert rows[0].count == 2

    # Duration buckets
    d_rows = engine.aggregate_dimension("target_duration")
    assert {r.category: r.count for r in d_rows} == {"40_49s": 2, "30_39s": 2}

    # Scene buckets
    s_rows = engine.aggregate_dimension("scene_count")
    assert {r.category: r.count for r in s_rows} == {"4_scenes": 2, "3_scenes": 2}

    # Audience
    a_rows = engine.aggregate_dimension("target_audience")
    assert {r.category for r in a_rows} == {"general_consumers", "tech_enthusiasts"}

    # Topic pattern derived from topic text
    t_rows = engine.aggregate_dimension("topic_pattern")
    assert {r.category: r.count for r in t_rows} == {"news": 2, "list": 2}

    # CTA classification
    c_rows = engine.aggregate_dimension("cta_strategy")
    assert {r.category: r.count for r in c_rows} == {"save": 4}

    # Platform always present
    p_rows = engine.aggregate_dimension("platform")
    assert [(r.category, r.count) for r in p_rows] == [("youtube", 4)]


def test_generate_insights_recommendations(tmp_path):
    db = Database(tmp_path / "insight.db")
    _populate(db)
    engine = PerformanceInsightsEngine(db=db)

    report = engine.generate_insights(min_samples=2)
    assert report.total_snapshots == 4
    assert "content_format" in report.dimensions

    fmt_findings = [f for f in report.findings if f.dimension == "content_format"]
    by_cat = {f.category: f for f in fmt_findings}
    assert by_cat["news"].direction == "above"
    assert by_cat["news"].reliable is True
    assert by_cat["news"].performance_ratio == 1.27
    assert by_cat["news"].confidence == 1.0
    assert by_cat["news"].recommendation.startswith("Prefer 'news'")
    assert by_cat["list"].direction == "below"
    assert by_cat["list"].reliable is True

    assert report.top_recommendations
    assert any("news" in r for r in report.top_recommendations)

    # With a higher minimum sample size, correlations become "limited"/unreliable
    strict = engine.generate_insights(min_samples=3)
    fmt_strict = {f.category: f for f in strict.findings if f.dimension == "content_format"}
    assert fmt_strict["news"].reliable is False
    assert fmt_strict["news"].confidence == round(2 / 3, 2)
    assert strict.top_recommendations == []


def test_feedback_multipliers_respect_min_samples(tmp_path):
    db = Database(tmp_path / "insight.db")
    _populate(db)
    engine = PerformanceInsightsEngine(db=db)

    mults = engine.get_feedback_multipliers(min_samples=2)
    assert mults["content_format"]["news"] == 1.27  # 87.5 / 68.75
    assert mults["content_format"]["list"] == 0.73  # 50.0 / 68.75
    assert mults["target_audience"]["general_consumers"] > 1.0
    assert mults["topic_pattern"]["news"] > 1.0

    # Below the minimum sample threshold every category is neutral (no-op)
    neutral = engine.get_feedback_multipliers(min_samples=5)
    assert all(m == 1.0 for m in neutral["content_format"].values())


def test_best_feedback_boost(tmp_path):
    db = Database(tmp_path / "insight.db")
    _populate(db)
    engine = PerformanceInsightsEngine(db=db)

    boost, reasons = engine.best_feedback_boost({"content_format": "news"}, min_samples=2)
    assert boost == 2.7  # (1.27 - 1.0) * 10
    assert any("news" in r for r in reasons)

    down, down_reasons = engine.best_feedback_boost({"content_format": "list"}, min_samples=2)
    assert down == -2.7
    assert any("underperforms" in r for r in down_reasons)

    # No reliable data -> neutral
    noneb, _ = engine.best_feedback_boost({"content_format": "news"})
    assert noneb == 0.0

    # Most relevant dimension wins, others and unknown keys are ignored
    multi, multi_reasons = engine.best_feedback_boost(
        {"content_format": "news", "target_audience": "tech_enthusiasts", "unknown": "x"},
        min_samples=2,
    )
    assert multi_reasons
    assert any("general" not in r for r in multi_reasons)


def test_category_bucket_helpers():
    assert PerformanceInsightsEngine.classify_topic_pattern("What is the history of Bitcoin?") == "story"
    assert PerformanceInsightsEngine.classify_topic_pattern("Top 5 hacks for developers") == "list"
    assert PerformanceInsightsEngine.classify_topic_pattern("New device launches today") == "general"
    assert PerformanceInsightsEngine.bucket_scenes(4) == "4_scenes"
    assert PerformanceInsightsEngine.bucket_scenes(6) == "5_plus_scenes"
    assert PerformanceInsightsEngine.bucket_duration(40) == "40_49s"
    assert PerformanceInsightsEngine.bucket_duration(35) == "30_39s"
    assert PerformanceInsightsEngine.classify_cta("Save this for later") == "save"
    assert PerformanceInsightsEngine.classify_cta("Share this with a friend") == "share"
    assert PerformanceInsightsEngine.classify_cta("Comment your thoughts below") == "discussion"
    assert PerformanceInsightsEngine.classify_cta("nonsense text") == "generic"