"""Small shared helpers."""

from __future__ import annotations

import re
import unicodedata


def slugify(text: str, *, max_length: int = 60) -> str:
    """Turn arbitrary user text into a safe filesystem slug."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[-\s]+", "-", text)
    return text[:max_length].rstrip("-") or "untitled"