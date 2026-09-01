"""OpenAI-compatible script provider.

Sends the topic to any OpenAI-compatible ``/chat/completions`` endpoint
(OpenAI, Azure, Ollama, LM Studio, ...) and parses the response into a
structured :class:`ShortScript`.

Configuration (see config/)::

    OPENAI_API_KEY    api key (required for hosted OpenAI; optional for local)
    OPENAI_BASE_URL   base URL, default https://api.openai.com/v1
    OPENAI_MODEL      model id, default gpt-4o-mini
    OPENAI_TEMPERATURE  sampling temperature
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

from generators.base import ScriptProvider, ScriptProviderError
from generators.models import ScriptSegment, ShortScript
from generators.prompt_templates import SYSTEM_PROMPT, build_user_prompt

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


class OpenAICompatibleProvider(ScriptProvider):
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
        self.temperature = float(temperature)
        self.timeout = timeout
        # Whitelist to avoid accidentally printing keys.
        self._safe_base = self.base_url

    def generate(self, topic: str, **kwargs) -> ShortScript:
        topic = topic.strip()
        if not topic:
            raise ValueError("topic must not be empty")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(topic)},
            ],
            "temperature": self.temperature,
        }
        if kwargs.get("response_format"):
            payload["response_format"] = kwargs["response_format"]

        url = f"{self.base_url}/chat/completions"
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ScriptProviderError(f"LLM request to {self.base_url} failed: {exc}") from exc

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise ScriptProviderError("Unexpected LLM response shape") from exc

        return self._parse(content, topic=topic)

    @staticmethod
    def _parse(content: str, topic: str) -> ShortScript:
        raw = _extract_json(content)
        try:
            if isinstance(raw, dict):
                segments = raw.get("segments") or []
            else:
                raise ValueError("not a json object")
        except (ValueError, AttributeError) as exc:
            raise ScriptProviderError("LLM response was not valid JSON") from exc

        try:
            parsed_segments = [
                ScriptSegment.model_validate({"kind": seg.get("kind"), "text": seg.get("text")})
                for seg in segments
            ]
            return ShortScript(
                topic=topic,
                title=str(raw.get("title") or _default_title(topic)),
                segments=parsed_segments,
                provider=OpenAICompatibleProvider.name,
            )
        except Exception as exc:
            raise ScriptProviderError(f"LLM script failed validation: {exc}") from exc


def _extract_json(content: str) -> Any:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end != -1:
            return json.loads(content[start : end + 1])
        raise


def _default_title(topic: str) -> str:
    return topic.strip().title()