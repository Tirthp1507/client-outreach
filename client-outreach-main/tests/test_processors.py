"""Tests for text cleaning, deduplication, ranking, and summarization."""

from collectors.models import RawContentItem
from processors import (
    ContentCleaner,
    ContentDeduplicator,
    ContentRanker,
    ContentSummarizer,
    process_content_batch,
)
from processors.deduplicator import canonicalize_url, token_jaccard_similarity


def test_cleaner_strips_html_and_boilerplate():
    raw_html = "<p>This is <b>bold</b> and &amp; decoded. <script>alert(1)</script> The post appeared first on Tech.</p>"
    clean = ContentCleaner.clean_text(raw_html)
    assert "<p>" not in clean
    assert "<b>" not in clean
    assert "alert(1)" not in clean
    assert "&" in clean
    assert "appeared first on" not in clean.lower()


def test_cleaner_cleans_title():
    raw = "Top 3 Productivity Hacks - TechCrunch [Video]"
    clean = ContentCleaner.clean_title(raw)
    assert clean == "Top 3 Productivity Hacks"


def test_canonicalize_url_strips_tracking():
    url1 = "https://example.com/post?utm_source=twitter&utm_medium=social&id=123"
    canon1 = canonicalize_url(url1)
    assert "utm_source" not in canon1
    assert "id=123" in canon1

    url2 = "https://EXAMPLE.com/post/"
    canon2 = canonicalize_url(url2)
    assert canon2 == "https://example.com/post"


def test_deduplicator_catches_url_and_fuzzy_title():
    dedup = ContentDeduplicator(similarity_threshold=0.7)
    item1 = RawContentItem(
        id="1", source_name="FeedA", title="How to master Python in 30 days", url="https://example.com/python-guide?utm_source=rss", content="Guide details"
    )
    item2 = RawContentItem(
        id="2", source_name="FeedB", title="How to master Python in 30 days", url="https://example.com/python-guide", content="Duplicate URL"
    )
    item3 = RawContentItem(
        id="3", source_name="FeedC", title="How to master Python in 30 days easily", url="https://other.com/py", content="Very similar title"
    )
    item4 = RawContentItem(
        id="4", source_name="FeedD", title="Complete guide to quantum computing", url="https://quantum.com/intro", content="Completely different"
    )

    unique, dups = dedup.deduplicate([item1, item2, item3, item4])
    assert len(unique) == 2
    assert dups == 2
    assert unique[0].id == "1"
    assert unique[1].id == "4"


def test_ranker_scores_hook_keywords():
    ranker = ContentRanker()
    item_hook = RawContentItem(
        id="h1", source_name="Tech", title="Top 3 mistakes beginners make with AI", url="https://a.com", content="Here are three big mistakes that beginners constantly make with AI models."
    )
    item_plain = RawContentItem(
        id="p1", source_name="Notes", title="Weekly software release notes", url="https://b.com", content="Patch 1.2 is out with bug fixes."
    )

    scored = ranker.rank_items([(item_hook, item_hook.content), (item_plain, item_plain.content)])
    assert len(scored) == 2
    assert scored[0][0].id == "h1"
    assert scored[0][2] > scored[1][2]  # item_hook has higher score


def test_summarizer_extracts_sentences_and_topic():
    summarizer = ContentSummarizer()
    title = "Top 3 Productivity Hacks"
    body = "First hack is timeboxing. Second hack is turning off notifications. Third hack is daily reviews. This is the conclusion."
    summary = summarizer.summarize(title, body, max_sentences=2)
    assert "First hack" in summary
    assert "Second hack" in summary

    topic = summarizer.suggest_topic("Deep Dive: The Future of Autonomous Coding Agents", body)
    assert "The Future of Autonomous Coding Agents" in topic


def test_process_content_batch_end_to_end():
    items = [
        RawContentItem(id="a", source_name="A", title="Why AI will change everything", url="https://a.com/1", content="Artificial intelligence is advancing at an unprecedented pace across all industries."),
        RawContentItem(id="b", source_name="B", title="Why AI will change everything", url="https://b.com/2", content="Duplicate title story"),
        RawContentItem(id="c", source_name="C", title="5 secret tips for productivity", url="https://c.com/3", content="Here are five secret tips to get more done in less time every single day."),
    ]
    batch = process_content_batch(items)
    assert batch.total_input == 3
    assert batch.total_duplicates_removed == 1
    assert batch.total_valid == 2
    assert len(batch.candidates) == 2
    assert batch.candidates[0].score >= batch.candidates[1].score