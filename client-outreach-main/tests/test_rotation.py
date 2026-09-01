"""Tests for Phase 10 visual & template diversity rotation."""

from strategy.rotation import TemplateRotation, VARIANTS
from strategy.topic_strategist import TopicStrategist
from processors.models import ProcessedCandidate


def _candidate(title: str = "Top 5 productivity tools for developers") -> ProcessedCandidate:
    return ProcessedCandidate(
        id="c_rot",
        source_name="Feed",
        source_url="https://feed.example/rot",
        raw_title=title,
        clean_title=title,
        topic_suggestion=title,
        summary="Key facts summarized.",
        clean_body="Body facts.",
        score=80.0,
    )


def test_rotation_never_repeats_immediately(tmp_path):
    rot = TemplateRotation(state_path=tmp_path / "rotation_state.json")
    assert rot.last_tag is None

    tags = []
    for _ in range(len(VARIANTS) + 2):
        variant = rot.next_variant()
        tags.append(variant["tag"])
        assert variant["tag"] in {v["tag"] for v in VARIANTS}
        assert variant["palette"] and variant["pace"] and variant["template"]

    for a, b in zip(tags, tags[1:]):
        assert a != b  # consecutive variants always differ


def test_rotation_persists_across_instances(tmp_path):
    state = tmp_path / "rotation_state.json"
    first = TemplateRotation(state_path=state)
    tag1 = first.next_variant()["tag"]
    assert state.exists()

    second = TemplateRotation(state_path=state)
    tag2 = second.next_variant()["tag"]
    # Resumed instance advances from persisted state, never repeating the last.
    assert tag2 != tag1
    assert second.state["turns"] == 2


def test_rotation_off_by_default_no_strategy_change(tmp_path):
    config = {"pipeline": {"output_dir": str(tmp_path)}, "strategy": {}}
    strategy = TopicStrategist(config).develop_strategy(_candidate())
    assert not any("Visual template rotation" in n for n in strategy.notes)
    assert strategy.scene_plans[1].visual_style == (
        "Clean data graphic / context B-roll showing key parties and facts"
    )


def test_rotation_applies_only_on_advance_rotation(tmp_path):
    config = {
        "pipeline": {"output_dir": str(tmp_path)},
        "strategy": {"diversity_rotation": True},
    }
    strategist = TopicStrategist(config)
    candidate = _candidate()

    # Selection/scoring passes never advance the rotation.
    scoring_strategy = strategist.develop_strategy(candidate, advance_rotation=False)
    assert not any("Visual template rotation" in n for n in scoring_strategy.notes)

    # The generation path advances once and applies the variant.
    gen1 = strategist.develop_strategy(candidate, advance_rotation=True)
    assert any("Visual template rotation" in n for n in gen1.notes)
    assert "palette" in gen1.scene_plans[1].visual_style
    first_palette = gen1.scene_plans[1].visual_style

    # The next generated video uses a different variant (palette + pacing).
    gen2 = strategist.develop_strategy(candidate, advance_rotation=True)
    assert any("Visual template rotation" in n for n in gen2.notes)
    assert gen2.scene_plans[1].visual_style != first_palette


def test_rotation_reset(tmp_path):
    rot = TemplateRotation(state_path=tmp_path / "rotation_state.json")
    rot.next_variant()
    assert rot.state["turns"] == 1
    rot.reset()
    assert rot.state == {"index": 0, "turns": 0, "last_tag": None}