import pytest


def test_template_provider_generates_structured_script():
    from generators import generate_script
    from generators.models import ScriptSegment

    script = generate_script("Top 3 productivity hacks")

    assert script.topic == "Top 3 productivity hacks"
    assert [s.kind for s in script.segments] == ["hook", "main", "cta"]
    assert all(isinstance(s, ScriptSegment) for s in script.segments)
    assert all(s.text.strip() for s in script.segments)
    assert script.hook is not None and script.cta is not None
    assert script.full_text  # spoken narration is non-empty


def test_template_provider_targets_50_seconds_max():
    from generators import generate_script

    script = generate_script("A much longer topic about time management for busy people")
    warnings = script.validate_timing(max_seconds=50)
    assert not warnings, warnings
    assert script.estimated_seconds <= 50


def test_template_provider_seed_is_deterministic():
    from generators import generate_script

    a = generate_script("Sleep better", seed=42)
    b = generate_script("Sleep better", seed=42)
    assert a.model_dump() == b.model_dump()
    c = generate_script("Sleep better", seed=7)
    assert a.model_dump() != c.model_dump()


def test_factory_rejects_unknown_provider():
    from generators.script_generator import build_provider

    with pytest.raises(ValueError, match="Unknown script provider"):
        build_provider({"pipeline": {"script_provider": "bogus"}})


def test_empty_topic_rejected():
    from generators import generate_script

    with pytest.raises(ValueError):
        generate_script("   ")  # type: ignore[arg-type]