"""Tests for MetadataGenerator (YouTube Shorts & Instagram Reels packaging)."""

from generators.models import ScriptSegment, ShortScript
from publishers import MetadataGenerator


def test_metadata_generator_creates_youtube_and_instagram_packages():
    script = ShortScript(
        topic="How to use AI daily",
        title="How to Use AI Daily to 10x Productivity",
        provenance={"source_name": "TechDaily", "source_url": "https://techdaily.com/article"},
        segments=[
            ScriptSegment(kind="hook", text="Here is what nobody tells you about AI productivity."),
            ScriptSegment(kind="main", text="Batch your prompt workflows, automate routine research, and review outputs daily."),
            ScriptSegment(kind="cta", text="Save this and follow for more."),
        ],
    )

    gen = MetadataGenerator()
    pkg = gen.generate(script, slug="how-to-use-ai-daily")

    assert "#Shorts" in pkg.youtube.title
    assert "TechDaily" in pkg.youtube.description
    assert len(pkg.youtube.tags) >= 5
    assert "KEY TAKEAWAYS" in pkg.youtube.description

    assert "⚡" in pkg.instagram.caption
    assert len(pkg.instagram.hashtags) >= 5
    assert pkg.thumbnail_timestamp_sec == 1.5