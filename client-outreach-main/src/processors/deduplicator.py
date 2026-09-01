"""Content deduplication using URL canonicalization and title similarity."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from typing import Sequence

from collectors.models import RawContentItem

RE_NON_ALPHANUM = re.compile(r"[^a-z0-9\s]")
TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "source", "ref_src", "feature"
}


def canonicalize_url(url: str) -> str:
    """Strip query tracking parameters and fragments from a URL."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        query_pairs = parse_qsl(parsed.query)
        filtered_query = [(k, v) for k, v in query_pairs if k.lower() not in TRACKING_PARAMS]
        clean_query = urlencode(filtered_query)
        clean_path = parsed.path.rstrip("/")
        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            clean_path,
            parsed.params,
            clean_query,
            "",  # drop fragment
        ))
    except Exception:
        return url.strip().lower().rstrip("/")


def title_token_set(title: str) -> set[str]:
    """Extract normalized word tokens for fuzzy duplicate detection."""
    clean = RE_NON_ALPHANUM.sub(" ", title.lower())
    return {w for w in clean.split() if len(w) > 2}


def token_jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Compute Jaccard similarity index between two token sets."""
    if not tokens_a or not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    return len(tokens_a & tokens_b) / len(union)


class ContentDeduplicator:
    """Identifies and filters duplicate content items across sources and batches."""

    def __init__(self, similarity_threshold: float = 0.75) -> None:
        self.similarity_threshold = similarity_threshold
        self.seen_urls: set[str] = set()
        self.seen_titles: list[tuple[str, set[str]]] = []

    def is_duplicate(self, item: RawContentItem) -> bool:
        """Check if an item is a duplicate based on URL or title similarity."""
        canon_url = canonicalize_url(item.url)
        if canon_url and canon_url in self.seen_urls:
            return True

        tokens = title_token_set(item.title)
        if not tokens:
            return False

        for _, past_tokens in self.seen_titles:
            sim = token_jaccard_similarity(tokens, past_tokens)
            if sim >= self.similarity_threshold:
                return True

        # Not a duplicate -> record it
        if canon_url:
            self.seen_urls.add(canon_url)
        self.seen_titles.append((item.title, tokens))
        return False

    def deduplicate(self, items: Sequence[RawContentItem]) -> tuple[list[RawContentItem], int]:
        """Deduplicate a sequence of items, returning unique items and duplicate count."""
        unique: list[RawContentItem] = []
        dup_count = 0
        for item in items:
            if self.is_duplicate(item):
                dup_count += 1
            else:
                unique.append(item)
        return unique, dup_count