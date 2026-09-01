"""Phase 8 QA: new checks (audio presence, clichés, subtitle readability)."""

from pathlib import Path

from generators.models import Scene, ScriptSegment, ShortScript
from pipeline.quality import QualityValidator


def _script(extra_main_text=""):
    return ShortScript(
        topic="Python Optimisation",
        title="Python Optimisation",
        segments=[
            ScriptSegment(kind="hook", text="Why is everyone talking about the new Python release? Here is the real breakdown."),
            ScriptSegment(kind="main", text="Profiling your code reveals the real bottleneck and then you fix it step by step." + extra_main_text),
            ScriptSegment(kind="cta", text="Follow for daily breakdowns and save this for later."),
        ],
        scenes=[
            Scene(scene_index=1, kind="hook", narration="h", visual_description="Alert headline", broll_keywords=["tech"]),
            Scene(scene_index=2, kind="main", narration="m", visual_description="Code screen", broll_keywords=["python"]),
            Scene(scene_index=3, kind="cta", narration="c", visual_description="Outro card", broll_keywords=["social"]),
        ],
    )


def test_cliche_detection_warns(tmp_path):
    sub = tmp_path / "sub.ass"
    sub.write_text("Dialogue: 0,0:00:00.10,0:00:03.70,Default,,0,0,0,,Hello there", encoding="utf-8")
    validator = QualityValidator()
    report = validator.validate(
        script=_script(extra_main_text=" This tool is a total game-changer. "),
        audio_path=None,
        subtitle_path=sub,
    )
    cliche = next(c for c in report.checks if c.name == "cliche_word_check")
    assert cliche.status == "WARN"
    assert cliche.score == 3.0


def test_no_cliche_passes():
    validator = QualityValidator()
    report = validator.validate(script=_script(), audio_path=None)
    cliche = next(c for c in report.checks if c.name == "cliche_word_check")
    assert cliche.status == "PASS"


def test_audio_presence_passes_with_real_file(tmp_path):
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"0" * 20_000)
    report = QualityValidator().validate(script=_script(), audio_path=audio)
    check = next(c for c in report.checks if c.name == "audio_presence")
    assert check.status == "PASS"


def test_audio_presence_none_is_warn_not_fail():
    report = QualityValidator().validate(script=_script(), audio_path=None)
    check = next(c for c in report.checks if c.name == "audio_presence")
    assert check.status == "WARN"


def test_audio_presence_tiny_file_fails(tmp_path):
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"0" * 20)
    report = QualityValidator().validate(script=_script(), audio_path=audio)
    check = next(c for c in report.checks if c.name == "audio_presence")
    assert check.status == "FAIL"


def test_subtitle_too_long_cue_warns(tmp_path):
    sub = tmp_path / "sub.ass"
    sub.write_text("Dialogue: 0,0:00:00.10,0:01:00.10,Default,,0,0,0,,way too long on screen", encoding="utf-8")
    report = QualityValidator().validate(script=_script(), subtitle_path=sub)
    check = next(c for c in report.checks if c.name == "subtitle_readability")
    assert check.status == "WARN"


def test_subtitle_clean_cues_pass(tmp_path):
    sub = tmp_path / "sub.ass"
    sub.write_text("Dialogue: 0,0:00:00.10,0:00:03.70,Default,,0,0,0,,Clean cue here", encoding="utf-8")
    report = QualityValidator().validate(script=_script(), subtitle_path=sub)
    check = next(c for c in report.checks if c.name == "subtitle_readability")
    assert check.status == "PASS"


def test_visual_variety_passes_with_scenes_and_broll():
    report = QualityValidator().validate(script=_script(), audio_path=None)
    check = next(c for c in report.checks if c.name == "visual_variety")
    assert check.status == "PASS"
    assert check.score == 15.0