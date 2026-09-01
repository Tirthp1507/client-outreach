"""Content collector abstraction and registry."""

from __future__ import annotations

import logging
from typing import Any

from collectors.base import BaseCollector, CollectorError
from collectors.models import CollectionBatch, RawContentItem, generate_item_id
from collectors.reddit_collector import RedditCollector
from collectors.rss_collector import RSSCollector

logger = logging.getLogger(__name__)

COLLECTOR_REGISTRY: dict[str, type[BaseCollector]] = {
    "rss": RSSCollector,
    "reddit": RedditCollector,
}


def build_collector(name: str, config: dict[str, Any] | None = None) -> BaseCollector:
    """Instantiate a collector by name."""
    cls = COLLECTOR_REGISTRY.get(name.lower())
    if cls is None:
        raise CollectorError(f"Unknown collector {name!r}. Available: {list(COLLECTOR_REGISTRY)}")
    return cls(name=name, config=config)


def collect_all_sources(
    config: dict[str, Any],
    sources: list[str] | None = None,
    limit: int = 20,
) -> CollectionBatch:
    """Run all configured collectors and aggregate into a CollectionBatch."""
    collectors_cfg = config.get("collectors", {})
    target_sources = sources or list(COLLECTOR_REGISTRY.keys())

    batch = CollectionBatch()

    for src_name in target_sources:
        src_cfg = collectors_cfg.get(src_name, {})
        # If enabled is explicitly false in config, skip
        if src_cfg.get("enabled") is False:
            continue

        batch.sources_attempted.append(src_name)
        try:
            collector = build_collector(src_name, config=src_cfg)
            items = collector.collect(limit=limit)
            batch.items.extend(items)
            batch.sources_succeeded.append(src_name)
        except Exception as exc:
            err_msg = f"Collector {src_name} failed: {exc}"
            logger.error(err_msg)
            batch.sources_failed.append(src_name)
            batch.errors.append(err_msg)

    batch.total_items = len(batch.items)
    return batch


__all__ = [
    "BaseCollector",
    "CollectionBatch",
    "CollectorError",
    "RawContentItem",
    "RedditCollector",
    "RSSCollector",
    "build_collector",
    "collect_all_sources",
    "generate_item_id",
]