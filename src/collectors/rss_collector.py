"""RSS / Atom feed collector."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any
import requests

from collectors.base import BaseCollector
from collectors.models import RawContentItem, generate_item_id

logger = logging.getLogger(__name__)

DEFAULT_FEEDS = [
    {
        "name": "Hacker News",
        "url": "https://news.ycombinator.com/rss",
        "category": "tech",
    },
    {
        "name": "BBC Technology",
        "url": "http://feeds.bbci.co.uk/news/technology/rss.xml",
        "category": "tech",
    },
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AIContentAutomation/1.0"


def _clean_xml_text(elem: ET.Element | None) -> str:
    if elem is None or elem.text is None:
        return ""
    return elem.text.strip()


def _local_tag(elem: ET.Element) -> str:
    return elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag


def parse_feed_xml(xml_content: str | bytes, source_name: str) -> list[RawContentItem]:
    """Parse RSS 2.0 or Atom 1.0 XML into RawContentItem models."""
    items: list[RawContentItem] = []
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        logger.warning("Failed to parse XML for %s: %s", source_name, exc)
        return items

    # RSS 2.0 / RSS 1.0 items
    rss_items = [e for e in root.iter() if _local_tag(e) == "item"]
    if rss_items:
        for item in rss_items:
            title = next((_clean_xml_text(c) for c in item if _local_tag(c) == "title"), "")
            link = next((_clean_xml_text(c) for c in item if _local_tag(c) == "link"), "")
            guid = next((_clean_xml_text(c) for c in item if _local_tag(c) == "guid"), "") or link
            desc = next((_clean_xml_text(c) for c in item if _local_tag(c) in ("encoded", "content", "description")), "")
            pub_date = next((_clean_xml_text(c) for c in item if _local_tag(c) in ("pubDate", "published")), "")
            author = next((_clean_xml_text(c) for c in item if _local_tag(c) in ("author", "creator")), "")
            tags = [_clean_xml_text(c) for c in item if _local_tag(c) == "category" and _clean_xml_text(c)]

            if not title and not desc:
                continue

            item_id = generate_item_id(source_name, guid or link, title)
            items.append(
                RawContentItem(
                    id=item_id,
                    source_name=source_name,
                    source_type="rss",
                    title=title,
                    url=link or guid,
                    content=desc,
                    author=author or None,
                    published_at=pub_date or None,
                    tags=tags,
                )
            )
        return items

    # Atom feed entries
    atom_entries = [e for e in root.iter() if _local_tag(e) == "entry"]
    for entry in atom_entries:
        title = next((_clean_xml_text(c) for c in entry if _local_tag(c) == "title"), "")
        
        # Link in atom can have href attribute
        link_elem = next((c for c in entry if _local_tag(c) == "link"), None)
        link = ""
        if link_elem is not None:
            link = link_elem.attrib.get("href", "") or _clean_xml_text(link_elem)

        id_elem = next((c for c in entry if _local_tag(c) == "id"), None)
        guid = _clean_xml_text(id_elem) or link

        content = next((_clean_xml_text(c) for c in entry if _local_tag(c) in ("content", "summary")), "")
        pub_date = next((_clean_xml_text(c) for c in entry if _local_tag(c) in ("published", "updated")), "")
        
        author = next(
            (_clean_xml_text(c) for c in entry.iter() if _local_tag(c) in ("name", "author", "creator") and _clean_xml_text(c)),
            "",
        )

        if not title and not content:
            continue

        item_id = generate_item_id(source_name, guid or link, title)
        items.append(
            RawContentItem(
                id=item_id,
                source_name=source_name,
                source_type="rss",
                title=title,
                url=link or guid,
                content=content,
                author=author or None,
                published_at=pub_date or None,
            )
        )

    return items


class RSSCollector(BaseCollector):
    """Fetches articles from a list of RSS/Atom feeds."""

    def __init__(self, name: str = "rss", config: dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self.feeds = self.config.get("feeds") or DEFAULT_FEEDS
        self.timeout = self.config.get("timeout", 10)

    def collect(self, limit: int = 20) -> list[RawContentItem]:
        """Fetch items across all configured feeds."""
        all_items: list[RawContentItem] = []
        headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"}

        for feed in self.feeds:
            feed_name = feed.get("name", "RSS Feed")
            feed_url = feed.get("url")
            if not feed_url:
                continue

            logger.info("Fetching RSS feed: %s (%s)", feed_name, feed_url)
            try:
                resp = requests.get(feed_url, headers=headers, timeout=self.timeout)
                if resp.status_code != 200:
                    logger.warning("Feed %s returned status %s", feed_name, resp.status_code)
                    continue

                feed_items = parse_feed_xml(resp.content, source_name=feed_name)
                all_items.extend(feed_items[:limit])
                logger.info("Collected %d items from %s", len(feed_items[:limit]), feed_name)
            except Exception as exc:
                logger.warning("Failed to collect from feed %s (%s): %s", feed_name, feed_url, exc)

        return all_items