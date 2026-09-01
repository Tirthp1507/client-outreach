"""Platform metadata and thumbnail packaging for YouTube Shorts and Instagram Reels."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from generators.models import ShortScript
from video.ffmpeg_utils import has_ffmpeg, run_ffmpeg

logger = logging.getLogger(__name__)


class YouTubeMetadata(BaseModel):
    title: str
    description: str
    tags: list[str] = Field(default_factory=list)
    category_id: str = "28"  # Science & Technology


class InstagramMetadata(BaseModel):
    caption: str
    reels_sound_hint: str = "Original Voiceover / Trending Speech"
    hashtags: list[str] = Field(default_factory=list)


class PlatformMetadataPackage(BaseModel):
    topic: str
    slug: str
    youtube: YouTubeMetadata
    instagram: InstagramMetadata
    thumbnail_timestamp_sec: float = 1.5
    thumbnail_path: str | None = None


class MetadataGenerator:
    """Generates optimized viral metadata for YouTube Shorts and Instagram Reels."""

    def generate(
        self,
        script: ShortScript,
        slug: str,
        *,
        video_path: str | Path | None = None,
        output_dir: str | Path | None = None,
    ) -> PlatformMetadataPackage:
        clean_title = script.title or script.topic
        clean_title = re.sub(r'[^\w\s\-\:\"\']', '', clean_title).strip()

        # 1. YouTube Shorts Title (<= 70 chars with #Shorts)
        yt_title = f"{clean_title[:58]} #Shorts" if len(clean_title) > 58 else f"{clean_title} #Shorts"

        # Tags extraction
        base_tags = ["shorts", "tech", "ai", "technology", "news", "productivity", "innovation", "trending"]
        specific_words = [w.lower() for w in clean_title.split() if len(w) > 3 and w.lower() not in base_tags]
        tags = list(dict.fromkeys(specific_words[:4] + base_tags))

        # 2. YouTube Description
        hook_text = script.hook.text if script.hook else clean_title
        main_text = script.main.text if script.main else ""
        source_prov = script.provenance or {}
        credit_url = source_prov.get("source_url", "")
        source_name = source_prov.get("source_name", "Curated News")

        yt_desc_lines = [
            f"🔥 {hook_text}",
            "",
            "📌 KEY TAKEAWAYS:",
            f"{main_text}",
            "",
            f"📰 Source & Credit: {source_name}" + (f" ({credit_url})" if credit_url else ""),
            "",
            "🔔 Subscribe for daily short-form breakdowns on technology, AI, and productivity!",
            "",
            " ".join(f"#{t}" for t in tags[:6]),
        ]
        yt_description = "\n".join(yt_desc_lines)

        # 3. Instagram Caption
        ig_caption_lines = [
            f"⚡ {clean_title}",
            "",
            f"{hook_text}",
            "",
            f"💡 {main_text}",
            "",
            "👇 Drop your take in the comments! Save this for later 📌",
            "",
            " ".join(f"#{t}" for t in tags[:10]),
        ]
        ig_caption = "\n".join(ig_caption_lines)

        # 4. Thumbnail Frame Extraction
        thumb_path = None
        thumb_sec = 1.5
        if video_path and Path(video_path).exists() and has_ffmpeg():
            vid_p = Path(video_path)
            target_thumb = vid_p.with_name(f"{slug}_thumb.jpg")
            try:
                run_ffmpeg(
                    ["-ss", str(thumb_sec), "-i", str(vid_p), "-frames:v", "1", "-q:v", "2", "-y", str(target_thumb)]
                )
                if target_thumb.exists():
                    thumb_path = str(target_thumb)
                    logger.info("Extracted thumbnail frame -> %s", thumb_path)
            except Exception as exc:
                logger.warning("Failed to extract thumbnail frame: %s", exc)

        return PlatformMetadataPackage(
            topic=script.topic,
            slug=slug,
            youtube=YouTubeMetadata(
                title=yt_title,
                description=yt_description,
                tags=tags[:10],
            ),
            instagram=InstagramMetadata(
                caption=ig_caption,
                hashtags=tags[:10],
            ),
            thumbnail_timestamp_sec=thumb_sec,
            thumbnail_path=thumb_path,
        )