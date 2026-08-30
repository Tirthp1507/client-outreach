"""Video engine tests.

The compositor itself does not start without FFmpeg; these verify the module
loads, background resolution logic behaves, and the missing-ffmpeg error is
clear and actionable.
"""

import pytest


def test_find_ffmpeg_returns_path_or_none():
    from video.ffmpeg_utils import find_ffmpeg

    result = find_ffmpeg()
    assert result is None or isinstance(result, str)


def test_compose_without_ffmpeg_raises_actionable_error(tmp_path, monkeypatch):
    from video.compositor import FFmpegCompositor, MissingFFmpegError
    from video.ffmpeg_utils import find_ffmpeg

    if find_ffmpeg():
        pytest.skip("ffmpeg present on this machine; MissingFFmpegError path not exercised")

    (tmp_path / "voice.mp3").write_bytes(b"fakemp3")
    (tmp_path / "captions.ass").write_text("[Script Info]", encoding="utf-8")

    compositor = FFmpegCompositor({"video": {"background_mode": "solid"}})
    with pytest.raises(MissingFFmpegError, match="FFmpeg is required"):
        compositor.compose(
            voice_path=tmp_path / "voice.mp3",
            subtitle_path=tmp_path / "captions.ass",
            output_path=tmp_path / "out.mp4",
        )


def test_background_resolution_solid():
    from video.compositor import FFmpegCompositor

    comp = FFmpegCompositor({"video": {"background_mode": "solid"}})
    mode, args = comp._resolve_background()
    assert mode == "solid"
    assert "color=" in " ".join(args)


def test_background_resolution_auto_without_assets(tmp_path):
    from video.compositor import FFmpegCompositor

    comp = FFmpegCompositor(
        {
            "video": {
                "background_mode": "auto",
                "background_asset": str(tmp_path / "nope"),
            }
        }
    )
    mode, args = comp._resolve_background()
    assert mode == "solid"
    assert comp._background_vf(mode) is None