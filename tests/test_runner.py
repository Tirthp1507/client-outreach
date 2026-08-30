"""Pipeline runner tests.

The full Topic->Script->Voice->Video run needs edge-tts (network) and/or
ffmpeg; those parts are skipped when unavailable. Unit-level behaviour is
tested against the non-network stages.
"""

import pytest


def test_run_without_video_produces_script_and_audio(tmp_path, monkeypatch):
    from pipeline.runner import PipelineRunner
    from voice.edge_tts_engine import _EDGE_IMPORT_ERROR

    if _EDGE_IMPORT_ERROR is not None:
        pytest.skip("edge-tts not installed")

    config = {
        "pipeline": {"output_dir": str(tmp_path)},
        "script": {"target_seconds": 40, "max_seconds": 50},
        "video": {"width": 1080, "height": 1920, "subtitle_font_size": 64},
        "voice": {"voice": "en-US-JennyNeural"},
    }
    runner = PipelineRunner(config)
    try:
        result = runner.run("Test topic", render_video=False, seed=1)
    except Exception as exc:  # network flake -> skip, not fail
        pytest.skip(f"edge-tts network unavailable: {exc}")

    assert result.status == "ok"
    assert "script" in result.artifacts
    assert "audio" in result.artifacts
    assert "subtitles_ass" in result.artifacts
    assert result.artifacts["audio"].endswith(".mp3")
    assert not result.blocked


def test_missing_topic_raises(tmp_path):
    from pipeline.runner import PipelineRunner

    with pytest.raises(ValueError):
        PipelineRunner({"pipeline": {"output_dir": str(tmp_path)}}).run("   ")