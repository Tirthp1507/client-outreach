"""Script generation facade — pick a provider from config and generate."""

from __future__ import annotations

from typing import Any

from generators.base import ScriptProvider, ScriptProviderError  # noqa: F401
from generators.models import ShortScript
from generators.openai_generator import OpenAICompatibleProvider
from generators.template_generator import TemplateScriptProvider

PROVIDERS = {
    "template": TemplateScriptProvider,
    "openai": OpenAICompatibleProvider,
}


def build_provider(
    config: dict[str, Any] | None = None, *, provider: str | None = None
) -> ScriptProvider:
    """Construct the configured script provider.

    Selection key: ``script_provider`` in config, overridable via
    ``SCRIPT_PROVIDER`` env var or the ``provider`` argument.
    """
    config = config or {}
    script_cfg = config.get("script", {})
    pipeline_cfg = config.get("pipeline", {})
    provider_name = (
        provider
        or script_cfg.get("provider")
        or pipeline_cfg.get("script_provider")
        or "template"
    )
    provider_name = str(provider_name).strip().lower()

    if provider_name == "template":
        return TemplateScriptProvider()

    if provider_name == "openai":
        oa = script_cfg.get("openai", {})
        return OpenAICompatibleProvider(
            api_key=oa.get("api_key"),
            base_url=oa.get("base_url"),
            model=oa.get("model"),
            temperature=oa.get("temperature", 0.7),
        )

    raise ValueError(
        f"Unknown script provider {provider_name!r}; choose from {sorted(PROVIDERS)}"
    )


def generate_script(
    topic: str,
    config: dict[str, Any] | None = None,
    *,
    provider: str | None = None,
    seed: int | None = None,
) -> ShortScript:
    """Generate a structured :class:`ShortScript` for ``topic``."""
    script_cfg = (config or {}).get("script", {})
    target_seconds = script_cfg.get("target_seconds", 40)
    chosen = build_provider(config, provider=provider)
    return chosen.generate(
        topic, target_seconds=target_seconds, seed=seed
    )