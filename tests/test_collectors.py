"""Tests for content collectors and feed parsers."""

import pytest
from collectors import RawContentItem, CollectionBatch, generate_item_id
from collectors.rss_collector import parse_feed_xml, RSSCollector
from collectors.reddit_collector import RedditCollector

SAMPLE_RSS_2 = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Tech News</title>
    <link>https://example.com</link>
    <item>
      <title>Top 5 AI tools that will save you 10 hours a week</title>
      <link>https://example.com/ai-tools?utm_source=rss</link>
      <description>&lt;p&gt;Here are five powerful AI tools you need to know about today.&lt;/p&gt;</description>
      <pubDate>Mon, 29 Aug 2026 12:00:00 GMT</pubDate>
      <category>AI</category>
      <category>Productivity</category>
    </item>
    <item>
      <title>Why everyone is switching to local LLMs</title>
      <link>https://example.com/local-llms</link>
      <description>Local models are faster, private, and cheaper than cloud APIs.</description>
    </item>
  </channel>
</rss>
"""

SAMPLE_ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Engineering Blog</title>
  <link href="https://example.org/feed.xml" rel="self"/>
  <entry>
    <title>How we built a real-time video pipeline in Python</title>
    <link href="https://example.org/video-pipeline"/>
    <id>tag:example.org,2026:video-pipeline</id>
    <summary>A detailed walkthrough of our FFmpeg and Python architecture.</summary>
    <published>2026-08-29T10:00:00Z</published>
    <author><name>Jane Doe</name></author>
  </entry>
</feed>
"""


def test_item_id_generation_is_deterministic():
    id1 = generate_item_id("Tech", "https://example.com/1", "Hello World")
    id2 = generate_item_id("Tech", "https://example.com/1", "Hello World")
    id3 = generate_item_id("Tech", "https://example.com/2", "Hello World")
    assert id1 == id2
    assert id1 != id3
    assert len(id1) == 16


def test_parse_rss2_feed():
    items = parse_feed_xml(SAMPLE_RSS_2, source_name="Tech News")
    assert len(items) == 2
    assert items[0].title == "Top 5 AI tools that will save you 10 hours a week"
    assert "https://example.com/ai-tools" in items[0].url
    assert "AI" in items[0].tags
    assert items[1].title == "Why everyone is switching to local LLMs"


def test_parse_atom_feed():
    items = parse_feed_xml(SAMPLE_ATOM, source_name="Eng Blog")
    assert len(items) == 1
    assert items[0].title == "How we built a real-time video pipeline in Python"
    assert items[0].url == "https://example.org/video-pipeline"
    assert items[0].author == "Jane Doe"


def test_rss_collector_offline_empty_url():
    collector = RSSCollector("rss", {"feeds": [{"name": "Empty", "url": ""}]})
    items = collector.collect(limit=5)
    assert items == []