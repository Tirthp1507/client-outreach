"""Content cleaning and text normalization."""

from __future__ import annotations

import html
import re

# Regex patterns for HTML/boilerplate cleaning
RE_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
RE_HTML_TAGS = re.compile(r"<[^>]+>")
RE_MARKDOWN_LINKS = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
RE_URLS = re.compile(r"https?://\S+|www\.\S+")
RE_MULTISPACE = re.compile(r"[ \t]+")
RE_MULTILINE = re.compile(r"\n{3,}")
RE_TRAILING_BRAND = re.compile(r"\s*[-–—|•]\s*([A-Za-z0-9\s]+)$")

BOILERPLATE_PATTERNS = [
    re.compile(r"the post\b.+?\bappeared first on\b[^\.\n]*\.?", re.IGNORECASE),
    re.compile(r"read more\s*\.?\s*$", re.IGNORECASE),
    re.compile(r"continue reading\s*\.?\s*$", re.IGNORECASE),
    re.compile(r"comments\s*$", re.IGNORECASE),
    re.compile(r"submit comments?\s*$", re.IGNORECASE),
    re.compile(r"sign up for .+? newsletter\.?", re.IGNORECASE),
]


class ContentCleaner:
    """Cleans raw text, HTML content, and titles for pipeline processing."""

    @staticmethod
    def clean_html(raw_html: str) -> str:
        """Strip HTML tags, scripts, styles, and decode entities."""
        if not raw_html:
            return ""
        text = RE_SCRIPT_STYLE.sub(" ", raw_html)
        text = RE_HTML_TAGS.sub(" ", text)
        text = html.unescape(text)
        return text

    @staticmethod
    def clean_text(raw_text: str) -> str:
        """Strip markdown links, URLs, boilerplate, and excessive whitespace."""
        if not raw_text:
            return ""
        text = ContentCleaner.clean_html(raw_text)
        text = RE_MARKDOWN_LINKS.sub(r"\1", text)
        text = RE_URLS.sub(" ", text)

        for pattern in BOILERPLATE_PATTERNS:
            text = pattern.sub("", text)

        # Normalize whitespace
        lines = [RE_MULTISPACE.sub(" ", line).strip() for line in text.splitlines()]
        clean_lines = [line for line in lines if line]
        joined = "\n".join(clean_lines)
        return RE_MULTILINE.sub("\n\n", joined).strip()

    @staticmethod
    def clean_title(raw_title: str) -> str:
        """Clean titles by stripping HTML, brackets, and trailing source branding."""
        if not raw_title:
            return ""
        title = ContentCleaner.clean_html(raw_title)
        title = RE_MULTISPACE.sub(" ", title).strip()
        # Remove trailing tags like [video], (photos), [updated]
        title = re.sub(r"\s*\[(video|photos|updated|pdf|audio)\]\s*", "", title, flags=re.IGNORECASE)
        # Remove trailing brand like " | TechCrunch" if present
        title = RE_TRAILING_BRAND.sub("", title).strip()
        return title