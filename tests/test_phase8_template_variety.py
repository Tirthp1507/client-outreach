"""Phase 8: script/hook variety in the deterministic template provider."""

from generators import generate_script


def test_template_hook_variety_across_seeds():
    hooks = set()
    for seed in range(12):
        script = generate_script("Deep work habits", seed=seed)
        assert script.hook is not None
        hooks.add(script.hook.text)
    assert len(hooks) >= 4, f"expected varied hooks, got {len(hooks)}"


def test_template_main_variety_across_seeds():
    mains = set()
    for seed in range(12):
        script = generate_script("Deep work habits", seed=seed)
        assert script.main is not None
        mains.add(script.main.text)
    assert len(mains) >= 3


def test_template_segments_carry_broll_keywords():
    script = generate_script("Top 3 productivity hacks", seed=5)
    for segment in script.segments:
        assert segment.broll_keywords, f"{segment.kind} missing B-roll keywords"


def test_template_still_targets_budget():
    for seed in range(8):
        script = generate_script("Morning routines that actually stick", seed=seed * 3 + 1)
        assert not script.validate_timing(max_seconds=50), script.validate_timing(max_seconds=50)