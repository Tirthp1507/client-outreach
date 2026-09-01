"""Tests for QualityValidator."""

from pathlib import Path
from generators.models import ScriptSegment, ShortScript
from pipeline.quality import QualityValidator


def test_quality_validator_with_valid_artifacts(tmp_path):
    script = ShortScript(
        topic="Top Tech Trends",
        title="Top Tech Trends",
        segments=[
            ScriptSegment(kind="hook", text="Stop scrolling — this changes tech forever."),
            ScriptSegment(kind="main", text="Here is the breakdown of why this innovation matters for developers and creators."),
            ScriptSegment(kind="cta", text="Follow for daily tech breakdowns and save this for later."),
        ],
    )

    audio_p = tmp_path / "voice.mp3"
    audio_p.write_bytes(b"0" * 30000)  # > 20KB

    sub_p = tmp_path / "sub.ass"
    sub_p.write_text("Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,Hello world", encoding="utf-8")

    vid_p = tmp_path / "video.mp4"
    vid_p.write_bytes(b"0" * 150000)  # > 100KB

    validator = QualityValidator()
    report = validator.validate(
        script=script,
        audio_path=audio_p,
        subtitle_path=sub_p,
        video_path=vid_p,
    )

    assert report.overall_score >= 80.0
    assert report.passed is True
    assert len(report.checks) == 9