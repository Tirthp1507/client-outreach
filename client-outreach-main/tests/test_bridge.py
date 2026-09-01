"""Tests for candidate-to-script generator bridge."""

from generators.bridge import generate_script_from_candidate
from processors.models import ProcessedCandidate


def test_generate_script_from_candidate_template():
    cand = ProcessedCandidate(
        id="cand_123",
        source_name="Ars Technica",
        source_url="https://arstechnica.com/ai-update",
        raw_title="Major AI Breakthrough Announced by Researchers",
        clean_title="Major AI Breakthrough Announced by Researchers",
        topic_suggestion="Major AI Breakthrough",
        summary="Researchers developed a new model that runs 10x faster with 50% less power.",
        clean_body="Detailed body text explaining the neural architecture and memory optimizations.",
        score=78.5,
        reasons=["High interest keywords", "Ideal text length"],
    )

    config = {"script": {"target_seconds": 40}, "pipeline": {"script_provider": "template"}}
    script = generate_script_from_candidate(cand, config, seed=42)

    assert script.topic == "Major AI Breakthrough"
    assert script.hook is not None
    assert "Major AI Breakthrough" in script.hook.text
    assert script.main is not None
    assert script.cta is not None
    assert script.provenance["candidate_id"] == "cand_123"
    assert script.provenance["source_name"] == "Ars Technica"
    assert script.provenance["source_url"] == "https://arstechnica.com/ai-update"