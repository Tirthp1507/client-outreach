"""Phase 8: scene-aware caption grouping, per-scene-kind ASS styles, and scene header track."""

from voice.models import WordTiming
from voice.subtitle_aligner import (
    SCENE_KIND_STYLES,
    build_captions,
    scene_regions_from_timings,
    to_ass,
    to_scene_headers_ass,
)
from generators.models import Scene


def _timings(words, step=0.4):
    out = []
    t = 0.0
    for i, word in enumerate(words):
        out.append(WordTiming(text=word, start=round(t, 3), end=round(t + 0.35, 3), sequence=i))
        t += step
    return out


def _scenes():
    return [
        Scene(scene_index=1, kind="hook", narration="A", visual_description="Hook visual", broll_keywords=["alert"], estimated_duration=4.0),
        Scene(scene_index=2, kind="main", narration="B", visual_description="Main visual", broll_keywords=["code"], estimated_duration=12.0),
        Scene(scene_index=3, kind="cta", narration="C", visual_description="Outro visual", broll_keywords=["social"], estimated_duration=4.0),
    ]


def test_scene_regions_scale_to_audio_duration():
    words = _timings(["one", "two", "three", "four", "five", "six", "seven", "eight"], step=1.0)
    regions = scene_regions_from_timings(words, _scenes())
    assert len(regions) == 3
    assert regions[0]["kind"] == "hook"
    assert regions[2]["kind"] == "cta"
    assert regions[2]["end"] == words[-1].end
    # proportional: hook ~4 of 20s worth = 20% of 8s
    assert abs(regions[0]["end"] - 1.6) < 0.35


def test_captions_do_not_straddle_scene_boundaries():
    words = _timings(
        ["hook", "word", "one", "two", "three", "four", "five", "six", "seven", "cta", "done"],
        step=0.5,
    )
    regions = scene_regions_from_timings(words, _scenes())
    # Force a wide max so only scene boundaries trigger splits.
    caps = build_captions(words, max_line_chars=200, max_lines=10, scene_regions=regions)
    assert len(caps) >= 3
    for cap in caps:
        assert cap["scene_kind"] in ("hook", "main", "cta")


def test_to_ass_emits_scene_kind_styles():
    words = _timings(
        ["hook", "words", "are", "here", "then", "main", "talks", "now", "and", "cta", "follows"],
        step=0.5,
    )
    regions = scene_regions_from_timings(words, _scenes())
    caps = build_captions(words, max_line_chars=200, max_lines=10, scene_regions=regions)
    content = to_ass(caps, width=1080, height=1920, font_size=68, scene_kind_styles=SCENE_KIND_STYLES)

    assert "Style: Hook," in content
    assert "Style: Cta," in content
    assert str(int(68 * SCENE_KIND_STYLES["hook"]["font_scale"])) in [
        line for line in content.splitlines() if line.startswith("Style: Hook,")][0]


def test_scene_headers_track():
    regions = [
        {"start": 0.0, "end": 1.6, "kind": "hook", "label": "HOOK 1"},
        {"start": 1.6, "end": 6.4, "kind": "main", "label": "MAIN 2"},
    ]
    content = to_scene_headers_ass(regions, width=1080, height=1920)
    assert "Style: SceneHeader," in content
    assert "HOOK 1" in content
    assert "MAIN 2" in content
    dialogue = [l for l in content.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogue) == 2
    assert dialogue[0].split(",")[1] == "0:00:00.00"