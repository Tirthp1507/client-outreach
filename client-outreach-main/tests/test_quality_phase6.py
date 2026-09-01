"""Tests for upgraded QualityValidator with pacing, repetition, variety, and provenance checks."""

from pathlib import Path
from generators.models import Scene, ScriptSegment, ShortScript
from pipeline.quality import QualityValidator


def test_quality_validator_all_checks_passing(tmp_path):
    sub_file = tmp_path / "subs.ass"
    sub_file.write_text("[Events]\nDialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,Hello world", encoding="utf-8")

    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"0" * 200_000)

    script = ShortScript(
        topic="AI Revolution",
        title="AI Revolution",
        segments=[
            ScriptSegment(kind="hook", text="Why is everyone talking about the new AI revolution? Here is what you need to know.", visual_prompt="Alert headline"),
            ScriptSegment(kind="main", text="The latest breakthroughs are automating complex analytical workflows with unprecedented speed across global industries.", visual_prompt="Cyberpunk tech screen"),
            ScriptSegment(kind="cta", text="Save this video for later, follow for daily breakdowns, and drop your thoughts below.", visual_prompt="Outro card"),
        ],
        scenes=[
            Scene(scene_index=1, kind="hook", narration="Why is everyone...", visual_description="Scene 1 visual"),
            Scene(scene_index=2, kind="main", narration="The latest...", visual_description="Scene 2 visual"),
            Scene(scene_index=3, kind="cta", narration="Save this...", visual_description="Scene 3 visual"),
        ],
        provenance={"source_name": "Ars Technica", "source_url": "https://arstechnica.com"},
    )

    validator = QualityValidator()
    report = validator.validate(
        script=script,
        video_path=vid_file,
        subtitle_path=sub_file,
    )

    assert report.passed is True
    assert report.overall_score >= 80.0
    check_names = {c.name for c in report.checks}
    assert "hook_strength" in check_names
    assert "content_repetition" in check_names
    assert "pacing_and_budget" in check_names
    assert "visual_variety" in check_names
    assert "source_provenance" in check_names