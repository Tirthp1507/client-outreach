"""Tests for animated word-level karaoke ASS subtitles."""

from voice.models import WordTiming
from voice.subtitle_aligner import build_captions, to_ass


def test_to_ass_animated_highlight_generates_word_events():
    timings = [
        WordTiming(text="Stop", start=0.0, end=0.4),
        WordTiming(text="scrolling", start=0.4, end=0.9),
        WordTiming(text="right", start=0.9, end=1.3),
        WordTiming(text="now", start=1.3, end=1.8),
    ]

    captions = build_captions(timings, max_line_chars=30, max_lines=2)
    assert len(captions) == 1
    assert len(captions[0]["words"]) == 4

    ass_text = to_ass(captions, animated_highlight=True)

    # Should contain 4 dialogue events, one highlighting each word
    dialogue_lines = [line for line in ass_text.splitlines() if line.startswith("Dialogue:")]
    assert len(dialogue_lines) == 4
    assert r"{\c&H0000FFFF&}Stop" in dialogue_lines[0]
    assert r"{\c&H0000FFFF&}scrolling" in dialogue_lines[1]
    assert r"{\c&H0000FFFF&}right" in dialogue_lines[2]
    assert r"{\c&H0000FFFF&}now" in dialogue_lines[3]