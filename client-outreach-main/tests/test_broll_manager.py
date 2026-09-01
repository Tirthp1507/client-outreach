"""Tests for BrollManager and multi-scene script models."""

from pathlib import Path
from generators.models import Scene, ScriptSegment, ShortScript
from video.broll_manager import BrollManager


def test_short_script_all_scenes_automatic_construction():
    script = ShortScript(
        topic="AI Productivity",
        title="AI Productivity",
        segments=[
            ScriptSegment(kind="hook", text="Stop scrolling right now.", visual_prompt="Cyberpunk AI interface", broll_keywords=["cyber", "ai"]),
            ScriptSegment(kind="main", text="Here is how to automate your daily tasks in three simple steps.", visual_prompt="Developer coding on laptop", broll_keywords=["coding", "laptop"]),
            ScriptSegment(kind="cta", text="Follow for daily tips.", visual_prompt="Subscribe button animation", broll_keywords=["social"]),
        ],
    )

    scenes = script.all_scenes
    assert len(scenes) == 3
    assert scenes[0].kind == "hook"
    assert scenes[0].broll_keywords == ["cyber", "ai"]
    assert scenes[1].kind == "main"
    assert scenes[1].visual_description == "Developer coding on laptop"
    assert scenes[2].kind == "cta"


def test_broll_manager_plans_scene_visuals(tmp_path):
    bg_dir = tmp_path / "backgrounds"
    bg_dir.mkdir(parents=True)
    (bg_dir / "tech_coding.mp4").write_bytes(b"0" * 100)
    (bg_dir / "cyber_ai.mp4").write_bytes(b"0" * 100)

    mgr = BrollManager({"video": {"background_asset": str(bg_dir)}})
    assets = mgr.list_available_assets()
    assert len(assets) == 2

    scenes = [
        Scene(scene_index=1, kind="hook", narration="Hook text", visual_description="AI cyber network", broll_keywords=["cyber"], estimated_duration=5.0),
        Scene(scene_index=2, kind="main", narration="Main text", visual_description="Developer coding", broll_keywords=["coding"], estimated_duration=15.0),
        Scene(scene_index=3, kind="cta", narration="CTA text", visual_description="Outro", broll_keywords=["social"], estimated_duration=5.0),
    ]

    plan = mgr.plan_scene_visuals(scenes, total_duration=25.0)
    assert len(plan) == 3
    assert plan[0].start_time == 0.0
    assert plan[0].asset_path.name == "cyber_ai.mp4"
    assert plan[1].asset_path.name == "tech_coding.mp4"
    assert plan[2].end_time == 25.0