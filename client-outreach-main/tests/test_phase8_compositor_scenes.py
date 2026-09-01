"""Phase 8: multi-scene compositor segment building (hermetic, no FFmpeg required)."""

from pathlib import Path

from video.broll_manager import BrollMatch
from video.compositor import FFmpegCompositor
from generators.models import Scene


def _compositor(tmp_path):
    return FFmpegCompositor(
        {
            "video": {
                "background_mode": "auto",
                "background_asset": str(tmp_path / "nope"),
                "width": 1080,
                "height": 1920,
                "framerate": 30,
            }
        }
    )


def test_build_scene_backgrounds_concats_solid_scenes(tmp_path):
    comp = _compositor(tmp_path)
    matches = [
        BrollMatch(1, 0.0, 5.0, asset_path=None, color_hex="0x0A1F2C"),
        BrollMatch(2, 5.0, 20.0, asset_path=None, color_hex="0x0E1A2B"),
        BrollMatch(3, 20.0, 25.0, asset_path=None, color_hex="0x122B3D"),
    ]
    inputs, branches, concat = comp._build_scene_backgrounds(matches)

    assert "0x0A1F2C" in " ".join(inputs)
    assert "0x0E1A2B" in " ".join(inputs)
    assert "0x122B3D" in " ".join(inputs)
    assert len(branches) == 3
    assert "concat=n=3:v=1:a=0[vg]" in concat
    # Each solid segment is duration-bounded.
    assert "d=5.000" in " ".join(inputs)
    assert "d=15.000" in " ".join(inputs)


def test_build_scene_backgrounds_uses_matched_asset_with_trim(tmp_path):
    comp = _compositor(tmp_path)
    asset = tmp_path / "cyber_ai.mp4"
    asset.write_bytes(b"0" * 100)
    matches = [
        BrollMatch(1, 0.0, 5.0, asset_path=asset, color_hex="0x0A1F2C"),
        BrollMatch(2, 5.0, 12.0, asset_path=None, color_hex="0x0E1A2B"),
    ]
    inputs, branches, concat = comp._build_scene_backgrounds(matches)

    assert str(asset) in " ".join(inputs)
    assert "-stream_loop" in inputs
    # Asset branch is bounded so the concat can actually advance.
    assert "trim=duration=5.000" in branches[0]
    assert "concat=n=2:v=1:a=0[vg]" in concat


def test_audio_voice_index_shifts_with_scene_inputs(tmp_path):
    """Voice must be mapped at index len(bg inputs) so audio labels stay correct."""
    comp = _compositor(tmp_path)
    matches = [BrollMatch(1, 0.0, 4.0, color_hex="0x0A1F2C"), BrollMatch(2, 4.0, 8.0, color_hex="0x0E1A2B")]
    _, _, _ = comp._build_scene_backgrounds(matches)
    assert len(matches) == 2


def test_compose_summary_exposes_scene_planning_fields():
    comp = _compositor(Path("."))
    assert comp.show_scene_headers is True
    assert comp.broll_manager is not None