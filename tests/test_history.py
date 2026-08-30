"""Tests for generation history and duplicate prevention store."""

from pathlib import Path
from pipeline.history import HistoryRecord, HistoryStore


def test_history_records_and_persists(tmp_path):
    hist_file = tmp_path / "history.json"
    store = HistoryStore(hist_file)

    assert not store.is_already_generated(candidate_id="c1", url="https://example.com/1")

    store.record(
        HistoryRecord(
            candidate_id="c1",
            topic="Top AI Tools",
            slug="top-ai-tools",
            source_name="Tech",
            source_url="https://example.com/1?utm_source=rss",
            source_title="Top AI Tools in 2026",
            score=75.0,
            video_path="/path/to/video.mp4",
        )
    )

    assert store.is_already_generated(candidate_id="c1")
    assert store.is_already_generated(url="https://example.com/1")
    assert store.is_already_generated(topic="Top AI Tools")
    assert not store.is_already_generated(candidate_id="c2")

    # Reload from disk
    reloaded = HistoryStore(hist_file)
    assert len(reloaded.records) == 1
    assert reloaded.is_already_generated(candidate_id="c1")