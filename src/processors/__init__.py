"""Content processing, deduplication, ranking, and summarization pipeline."""

from __future__ import annotations

import logging
from typing import Any, Sequence

from collectors.models import RawContentItem
from processors.cleaner import ContentCleaner
from processors.deduplicator import ContentDeduplicator
from processors.models import ProcessedCandidate, ProcessingBatch
from processors.ranker import ContentRanker
from processors.summarizer import ContentSummarizer

logger = logging.getLogger(__name__)


def process_content_batch(
    items: Sequence[RawContentItem],
    config: dict[str, Any] | None = None,
) -> ProcessingBatch:
    """Run cleaning, deduplication, ranking, and summarization on a raw content batch."""
    cfg = config or {}
    proc_cfg = cfg.get("processors", {})

    sim_thresh = proc_cfg.get("dedup_similarity_threshold", 0.75)
    min_words = proc_cfg.get("min_word_count", 5)

    cleaner = ContentCleaner()
    deduplicator = ContentDeduplicator(similarity_threshold=sim_thresh)
    ranker = ContentRanker()
    summarizer = ContentSummarizer()

    batch = ProcessingBatch(total_input=len(items))

    # 1. Deduplicate raw items
    unique_items, dup_count = deduplicator.deduplicate(items)
    batch.total_duplicates_removed = dup_count

    # 2. Clean items and filter out empties
    cleaned_pairs: list[tuple[RawContentItem, str, str]] = []
    for item in unique_items:
        clean_title = cleaner.clean_title(item.title)
        clean_body = cleaner.clean_text(item.content)
        word_count = len(clean_body.split())
        if word_count < min_words and len(clean_title.split()) < 3:
            continue
        cleaned_pairs.append((item, clean_title, clean_body))

    # 3. Rank items
    ranked = ranker.rank_items([(it, body) for it, _, body in cleaned_pairs])

    # Map back to titles
    title_map = {it.id: title for it, title, _ in cleaned_pairs}

    # 4. Summarize and build candidates
    candidates: list[ProcessedCandidate] = []
    for item, clean_body, score, breakdown, reasons in ranked:
        clean_title = title_map.get(item.id, item.title)
        summary = summarizer.summarize(clean_title, clean_body)
        topic_suggestion = summarizer.suggest_topic(clean_title, clean_body)

        candidate = ProcessedCandidate(
            id=item.id,
            source_name=item.source_name,
            source_url=item.url,
            raw_title=item.title,
            clean_title=clean_title,
            topic_suggestion=topic_suggestion,
            summary=summary,
            clean_body=clean_body,
            score=score,
            score_breakdown=breakdown,
            reasons=reasons,
            tags=item.tags,
            word_count=len(clean_body.split()),
        )
        candidates.append(candidate)

    batch.candidates = candidates
    batch.total_valid = len(candidates)
    return batch


__all__ = [
    "ContentCleaner",
    "ContentDeduplicator",
    "ContentRanker",
    "ContentSummarizer",
    "ProcessedCandidate",
    "ProcessingBatch",
    "process_content_batch",
]