"""Tests for Phase 9 performance-feedback integration: scorer, selector, and strategist."""

import json

from analytics.feedback import PerformanceFeedbackScorer
from analytics.models import PerformanceSnapshot, PlatformMetrics
from db.database import Database
from db.models import JobRecord, JobStatus
from pipeline.history import HistoryStore
from pipeline.selector import ContentSelector
from processors.models import ProcessedCandidate
from strategy.topic_strategist import TopicStrategist

NEWS_TITLE = "Tech giants settle landmark lawsuit for 5 billion dollars"
LIST_TITLE = "Top 5 productivity tools for developers"


def _candidate(cid: str, title: str, score: float) -> ProcessedCandidate:
    return ProcessedCandidate(
        id=cid,
        source_name="Feed",
        source_url=f"https://feed.example/{cid}",
        raw_title=title,
        clean_title=title,
        topic_suggestion=title,
        summary="Key facts summarized for short-form video.",
        clean_body="A concise body of facts used to drive the script narration.",
        score=score,
    )


def _add_snapshot(
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
    engagement: float,
) -> None:
    db.save_job(
        JobRecord(
            id=job_id,
            slug=job_id,
            topic=topic,
            status=JobStatus.PUBLISHED,
            content_format=fmt,
            hook_strategy=hook,
            target_audience=audience,
            strategy_json=json.dumps(
                {"scene_count": scenes, "target_duration_seconds": duration, "cta_strategy": cta}
            ),
        )
    )
    db.save_snapshot(
        PerformanceSnapshot(
            id=f"snap_{job_id}",
            job_id=job_id,
            slug=job_id,
            platform="youtube",
            metrics=PlatformMetrics(views=views, likes=int(views * 0.08), retention_rate_pct=80.0),
            engagement_score=engagement,
        )
    )


def _populate_balanced(db: Database) -> None:
    """2 high-performing news + 2 low-performing list snapshots (min_samples=2)."""
    _add_snapshot(
        db, "n1", fmt="news", hook="statistic_shock", audience="general_consumers",
        scenes=4, duration=40, cta="Save this to stay ahead and drop your take below",
        topic=NEWS_TITLE, views=5000, engagement=90.0,
    )
    _add_snapshot(
        db, "n2", fmt="news", hook="statistic_shock", audience="general_consumers",
        scenes=4, duration=40, cta="Save this to stay ahead and drop your take below",
        topic="Regulators probe record settlement in federal court",
        views=4500, engagement=85.0,
    )
    _add_snapshot(
        db, "l1", fmt="list", hook="curiosity_gap", audience="tech_enthusiasts",
        scenes=3, duration=35, cta="Bookmark this guide for later",
        topic=LIST_TITLE, views=1500, engagement=55.0,
    )
    _add_snapshot(
        db, "l2", fmt="list", hook="curiosity_gap", audience="tech_enthusiasts",
        scenes=3, duration=35, cta="Bookmark this guide for later",
        topic="Top 10 ways to speed up your workflow",
        views=1200, engagement=45.0,
    )


def test_scorer_neutral_without_signal(tmp_path):
    db = Database(tmp_path / "empty.db")
    scorer = PerformanceFeedbackScorer(db=db, config={})
    cand = _candidate("c_neutral", NEWS_TITLE, 80.0)

    assert scorer.has_signal is False
    assert scorer.score(cand) == 80.0
    assert scorer.explain(cand) == (0.0, [])


def test_scorer_has_signal_with_history(tmp_path):
    db = Database(tmp_path / "signal.db")
    _populate_balanced(db)
    scorer = PerformanceFeedbackScorer(db=db, config={"analytics": {"min_samples": 2}})

    assert scorer.has_signal is True
    news_cand = _candidate("c_news", NEWS_TITLE, 80.0)
    list_cand = _candidate("c_list", LIST_TITLE, 85.0)

    news_score = scorer.score(news_cand)
    list_score = scorer.score(list_cand)
    assert news_score == 82.7  # 80 + 2.7 from the learned news advantage
    assert list_score == 82.3  # 85 - 2.7 for the underperforming list format
    assert news_score > list_score


def test_selector_reranks_with_feedback(tmp_path):
    db = Database(tmp_path / "rerank.db")
    _populate_balanced(db)
    scorer = PerformanceFeedbackScorer(db=db, config={"analytics": {"min_samples": 2}})
    selector = ContentSelector(HistoryStore(tmp_path / "history.json"))

    list_cand = _candidate("c_list", LIST_TITLE, 85.0)
    news_cand = _candidate("c_news", NEWS_TITLE, 80.0)

    # Without feedback: raw score ordering is preserved (list raw 85 > news raw 80).
    plain = selector.select_candidates([list_cand, news_cand], limit=1)
    assert plain[0].id == "c_list"

    # With feedback: the outperforming news format is selected first.
    boosted = selector.select_candidates(
        [list_cand, news_cand], limit=1, feedback_scorer=scorer
    )
    assert boosted[0].id == "c_news"


def test_strategy_feedback_off_by_default(tmp_path):
    db = Database(tmp_path / "strat.db")
    _populate_balanced(db)
    cand = _candidate("c_news", NEWS_TITLE, 88.0)

    strategy = TopicStrategist(config={"strategy": {}}).develop_strategy(cand)
    assert strategy.short_form_potential_score == 96.6
    assert not any("Performance feedback" in n for n in strategy.notes)


def test_strategy_feedback_additively_boosts_potential(tmp_path):
    db = Database(tmp_path / "strat_fb.db")
    # 3 news snapshots (reliable at the default min_samples=3) + 1 low performer.
    for i, eng in enumerate((90.0, 85.0, 80.0)):
        _add_snapshot(
            db, f"n{i}", fmt="news", hook="statistic_shock", audience="general_consumers",
            scenes=4, duration=40, cta="Save this to stay ahead and drop your take below",
            topic=NEWS_TITLE, views=4000 + i * 500, engagement=eng,
        )
    _add_snapshot(
        db, "l1", fmt="list", hook="curiosity_gap", audience="tech_enthusiasts",
        scenes=3, duration=35, cta="Bookmark this guide for later",
        topic=LIST_TITLE, views=1200, engagement=45.0,
    )

    cand = _candidate("c_news", NEWS_TITLE, 88.0)
    boosted = TopicStrategist(
        config={"strategy": {}}, performance_feedback=True, feedback_db=db
    ).develop_strategy(cand)

    # news avg 85 vs benchmark (255+45)/4=75 -> multiplier 1.13 -> +1.3 pts
    assert boosted.short_form_potential_score == 97.9
    assert any("Performance feedback" in n for n in boosted.notes)
    assert any("adjusted from 96.6 to 97.9" in n for n in boosted.notes)