"""Content summarization and topic suggestion generator."""

from __future__ import annotations

import re


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using basic punctuation rules."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    # Split on sentence boundaries
    raw_sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    return [s.strip() for s in raw_sentences if len(s.strip()) > 10]


class ContentSummarizer:
    """Produces concise bullet summaries and punchy video topic suggestions."""

    def summarize(self, clean_title: str, clean_body: str, max_sentences: int = 3) -> str:
        """Create a 2-3 sentence overview from the cleaned content."""
        sentences = _split_sentences(clean_body)
        if not sentences:
            return clean_title

        selected = sentences[:max_sentences]
        return " ".join(selected)

    def suggest_topic(self, clean_title: str, clean_body: str) -> str:
        """Create a high-retention topic hook for the short video pipeline."""
        # If title already looks like a strong short topic, use it cleanly
        title_stripped = clean_title.strip()
        if len(title_stripped.split()) <= 8 and not title_stripped.endswith("?"):
            return title_stripped

        # Clean title if it contains colon or dash
        if ":" in title_stripped:
            parts = title_stripped.split(":", 1)
            prefix, rest = parts[0].strip(), parts[1].strip()
            if len(rest.split()) >= 3:
                return rest

        return title_stripped