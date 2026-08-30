from pathlib import Path

from voice.models import WordTiming
from voice.subtitle_aligner import build_captions, to_ass, to_srt


def _timings(words):
    out = []
    t = 0.0
    for i, word in enumerate(words):
        out.append(WordTiming(text=word, start=round(t, 3), end=round(t + 0.35, 3), sequence=i))
        t += 0.35
    return out


def test_build_captions_groups_words():
    words = _timings("one two three four five six seven eight nine ten".split())
    caps = build_captions(words, max_line_chars=7, max_lines=2)
    assert caps
    # text coverage: all words appear across captions
    joined = " ".join(c["text"] for c in caps)
    assert "one" in joined and "ten" in joined
    for c in caps:
        assert c["start"] < c["end"]


def test_build_captions_empty():
    assert build_captions([]) == []


def test_to_srt_format():
    caps = [{"start": 1.0, "end": 1.7, "text": "hello world"}]
    content = to_srt(caps)
    assert "1\n00:00:01,000 --> 00:00:01,700" in content
    assert "hello world" in content


def test_to_ass_format():
    caps = [{"start": 1.0, "end": 1.7, "text": "hello world"}]
    content = to_ass(caps, width=1080, height=1920, font_size=64)
    assert "[Script Info]" in content
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert "Dialogue:" in content
    assert "hello world" in content


def test_write_subtitle_files(tmp_path):
    from voice.subtitle_aligner import write_subtitle_files

    caps = [{"start": 0.0, "end": 1.0, "text": "first subtitle"}]
    paths = write_subtitle_files(caps, tmp_path / "clip", width=1080, height=1920)
    srt = Path(paths["srt"])
    ass = Path(paths["ass"])
    assert srt.exists() and ass.exists()
    assert "first subtitle" in srt.read_text(encoding="utf-8")
    assert "first subtitle" in ass.read_text(encoding="utf-8")