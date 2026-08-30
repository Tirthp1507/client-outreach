"""Tests for the Phase 10 Topic-Fatigue / Anti-Repetition diversity scorer."""

from analytics.diversity import DiversityScorer
from db.database import Database
from db.models import JobRecord, JobStatus
from pipeline.history import HistoryStore
from pipeline.selector import ContentSelector
from processors.models import ProcessedCandidate


def _candidate(cid: str, title: str, score: float = 80.0) -> ProcessedCandidate:
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


def _add_job(db: Database, job_id: str, topic: str, *, fmt: str = "news") -> None:
    db.save_job(
        JobRecord(
            id=job_id,
            slug=job_id,
            topic=topic,
            status=JobStatus.PENDING_REVIEW,
            content_format=fmt,
            hook_strategy="statistic_shock",
            target_audience="general_consumers",
        )
    )


NEWS_TITLE = "Tech giants settle landmark lawsuit for 5 billion dollars"


def test_diversity_inactive_with_empty_history(tmp_path):
    db = Database(tmp_path / "empty.db")
    scorer = DiversityScorer(db=db, config={})
    cand = _candidate("c1", NEWS_TITLE, 80.0)

    assert scorer.is_active is False
    assert scorer.has_signal is False
    assert scorer.explain(cand) == (0.0, [])
    assert scorer.score(cand) == 80.0


def test_topic_near_duplicate_is_penalized(tmp_path):
    db = Database(tmp_path / "dup.db")
    _add_job(db, "j_recent", NEWS_TITLE)
    scorer = DiversityScorer(db=db, config={"analytics": {}}, window=6)

    fresh = _candidate("fresh", "Top 5 productivity tools for developers", 85.0)
    dup = _candidate("dup", f"Follow-up: {NEWS_TITLE}", 85.0)

    # Near-duplicate topic gets a penalty; unrelated fresh candidate does not.
    dup_delta, dup_reasons = scorer.explain(dup)
    fresh_delta, fresh_reasons = scorer.explain(fresh)
    assert dup_delta < 0.0
    assert any("near-duplicate" in r for r in dup_reasons)
    assert fresh_delta == 0.0 or fresh_delta > dup_delta
    assert not any("near-duplicate" in r for r in fresh_reasons)


def test_category_fatigue_penalty(tmp_path):
    db = Database(tmp_path / "fatigue.db")
    # 3 consecutive news jobs -> news format / general audience are fatigued.
    for i in range(3):
        _add_job(db, f"n{i}", f"Regulators probe settlement case number {i}")
    scorer = DiversityScorer(db=db, config={"analytics": {}}, window=6)

    cand = _candidate("news_cand", "Regulators probe record settlement in federal court")
    delta, reasons = scorer.explain(cand)
    assert delta < 0.0
    assert any("overused" in r and "format" in r for r in reasons)

    # A non-news candidate is not hit by the format/audience fatigue.
    other = _candidate("list_cand", "Top 5 productivity tools for developers")
    o_delta, o_reasons = scorer.explain(other)
    assert not any("overused" in r for r in o_reasons)
    assert o_delta >= delta


def test_total_penalty_is_bounded(tmp_path):
    db = Database(tmp_path / "cap.db")
    for i in range(4):
        _add_job(db, f"n{i}", f"Regulators probe record settlement in federal court")
    scorer = DiversityScorer(db=db, config={"analytics": {}}, window=6)

    # Near-duplicate topic AND full-category fatigue -> capped by max penalty.
    cand = _candidate("news_cand", "Regulators probe record settlement in federal court")
    delta, reasons = scorer.explain(cand)
    assert reasons
    assert abs(delta) <= 5.0  # max_diversity_penalty default


def test_selector_reranks_away_from_fatigue(tmp_path):
    db = Database(tmp_path / "rerank.db")
    for i in range(3):
        _add_job(db, f"n{i}", f"Regulators probe settlement case number {i}")
    scorer = DiversityScorer(db=db, config={"analytics": {}}, window=6)
    selector = ContentSelector(HistoryStore(tmp_path / "history.json"))

    fatigued = _candidate("fatigued", "Regulators probe record settlement in federal court", 94.0)
    fresh = _candidate("fresh", "Top 5 productivity tools for developers", 90.0)

    plain = selector.select_candidates([fatigued, fresh], limit=1)
    assert plain[0].id == "fatigued"  # raw score ordering preserved

    diversified = selector.select_candidates([fatigued, fresh], limit=1, feedback_scorer=scorer)
    assert diversified[0].id == "fresh"


def test_diversity_window_scoping(tmp_path):
    db = Database(tmp_path / "window.db")
    for i in range(2):
        _add_job(db, f"n{i}", f"Regulators probe settlement case number {i}")
    narrow = DiversityScorer(db=db, config={"analytics": {}}, window=1)
    wide = DiversityScorer(db=db, config={"analytics": {}}, window=2)

    cand = _candidate("news_cand", "Regulators probe record settlement in federal court")
    _, narrow_reasons = narrow.explain(cand)
    _, wide_reasons = wide.explain(cand)

    # A single recent job cannot reach the fatigue threshold of 2.
    assert not any("overused" in r for r in narrow_reasons)
    # With the full recent window, the news/audience overuse is detected.
    assert any("overused" in r for r in wide_reasons)