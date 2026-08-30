"""Tests for ContentSelector layer."""

from pipeline.history import HistoryRecord, HistoryStore
from pipeline.selector import ContentSelector
from processors.models import ProcessedCandidate


def test_content_selector_filters_by_score_and_history(tmp_path):
    hist = HistoryStore(tmp_path / "history.json")
    hist.record(
        HistoryRecord(
            candidate_id="c1",
            topic="Already Done Topic",
            slug="already-done",
            source_url="https://a.com/1",
        )
    )

    c1 = ProcessedCandidate(
        id="c1", source_name="Feed", source_url="https://a.com/1", raw_title="A", clean_title="A", topic_suggestion="Already Done Topic", summary="S", clean_body="B", score=90.0
    )
    c2 = ProcessedCandidate(
        id="c2", source_name="Feed", source_url="https://a.com/2", raw_title="B", clean_title="B", topic_suggestion="High Score Topic", summary="S", clean_body="B", score=80.0
    )
    c3 = ProcessedCandidate(
        id="c3", source_name="Feed", source_url="https://a.com/3", raw_title="C", clean_title="C", topic_suggestion="Medium Score Topic", summary="S", clean_body="B", score=45.0
    )
    c4 = ProcessedCandidate(
        id="c4", source_name="Feed", source_url="https://a.com/4", raw_title="D", clean_title="D", topic_suggestion="Low Score Topic", summary="S", clean_body="B", score=20.0
    )

    selector = ContentSelector(hist)

    # c1 is in history (skipped), c4 is below min_score 30.0 (skipped)
    selected = selector.select_candidates([c1, c2, c3, c4], limit=2, min_score=30.0)
    assert len(selected) == 2
    assert selected[0].id == "c2"
    assert selected[1].id == "c3"