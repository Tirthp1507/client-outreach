"""Bridge to convert ProcessedCandidate models into strategy-directed ShortScript instances."""

from __future__ import annotations

from typing import Any

from generators.base import ScriptProviderError
from generators.models import ShortScript
from generators.openai_generator import OpenAICompatibleProvider
from generators.strategy_director import StrategyDirector
from processors.models import ProcessedCandidate
from strategy import TopicStrategist


def generate_script_from_candidate(
    candidate: ProcessedCandidate,
    config: dict[str, Any],
    *,
    provider: str | None = None,
    seed: int | None = None,
) -> ShortScript:
    """Generate a structured, strategy-directed ShortScript from a ProcessedCandidate."""
    prov_name = (
        provider
        or (config.get("pipeline", {}) or {}).get("script_provider", "template")
    ).lower()

    # 1. Develop strategic content plan
    strategist = TopicStrategist(config)
    strategy = strategist.develop_strategy(candidate, advance_rotation=True)

    if prov_name in ("template", "strategy_director", "default"):
        return StrategyDirector.direct_script(candidate, strategy, provider_name="strategy_director")

    if prov_name == "openai":
        openai_cfg = (config.get("script", {}) or {}).get("openai", {})
        llm = OpenAICompatibleProvider(
            api_key=openai_cfg.get("api_key"),
            base_url=openai_cfg.get("base_url"),
            model=openai_cfg.get("model"),
            temperature=openai_cfg.get("temperature", 0.7),
        )
        context_prompt = (
            f"Topic: {candidate.clean_title}\n"
            f"Source: {candidate.source_name}\n"
            f"Strategic Angle: {strategy.recommended_angle}\n"
            f"Content Format: {strategy.content_format.value}\n"
            f"Target Audience: {strategy.target_audience.value}\n"
            f"Hook Strategy: {strategy.hook_strategy.value}\n"
            f"Summary: {candidate.summary}\n"
            f"Context: {candidate.clean_body[:800]}"
        )
        script = llm.generate(context_prompt)
        script.topic = candidate.topic_suggestion
        script.provenance = {
            "candidate_id": candidate.id,
            "source_name": candidate.source_name,
            "source_url": candidate.source_url,
            "raw_title": candidate.raw_title,
            "clean_title": candidate.clean_title,
            "score": candidate.score,
            "score_reasons": candidate.reasons,
        }
        script.strategy = strategy.model_dump(mode="json")
        return script

    raise ScriptProviderError(f"Unsupported script provider {prov_name!r}")