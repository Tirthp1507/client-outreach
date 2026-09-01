"""Gemini AI script provider for Gemini 2.5 Flash.

Queries Google Gemini REST API using GEMINI_API_KEY and parses the response into a structured ShortScript.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from config import get_config
from generators.base import ScriptProvider, ScriptProviderError
from generators.models import ScriptSegment, ShortScript
from generators.prompt_templates import SYSTEM_PROMPT, build_user_prompt

DEFAULT_MODEL = "gemini-2.5-flash"


def _extract_json(text: str) -> Any:
    """Strip markdown codeblocks if present and parse raw JSON."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


class GeminiProvider(ScriptProvider):
    name = "gemini"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        timeout: float = 60.0,
    ) -> None:
        # Load environment via get_config() if missing
        cfg = get_config()
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or cfg.get("gemini_api_key")
        self.model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
        self.temperature = float(temperature)
        self.timeout = timeout

    def generate(self, topic: str, **kwargs: Any) -> ShortScript:
        topic = topic.strip()
        if not topic:
            raise ValueError("topic must not be empty")

        if not self.api_key:
            raise ScriptProviderError("GEMINI_API_KEY not configured in environment or config/.env")

        prompt = f"{SYSTEM_PROMPT}\n\n{build_user_prompt(topic)}"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "responseMimeType": "application/json",
            },
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as exc:
            raise ScriptProviderError(f"Gemini API request failed: {exc}") from exc

        return self._parse(content, topic=topic)

    @staticmethod
    def _parse(content: str, topic: str) -> ShortScript:
        try:
            raw = _extract_json(content)
            if isinstance(raw, dict):
                segments = raw.get("segments") or []
            else:
                raise ValueError("not a json object")
        except Exception as exc:
            raise ScriptProviderError(f"Gemini response was not valid JSON: {exc}") from exc

        parsed_segments = []
        for seg in segments:
            kind = seg.get("kind", "spoken_text")
            text = seg.get("text", "")
            parsed_segments.append(ScriptSegment(kind=kind, text=text))

        title = raw.get("title") or f"Script for {topic}"
        return ShortScript(title=title, topic=topic, segments=parsed_segments)
