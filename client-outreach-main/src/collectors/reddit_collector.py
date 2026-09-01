"""Public Reddit collector (no OAuth credentials required)."""

from __future__ import annotations

import logging
from typing import Any
import requests

from collectors.base import BaseCollector
from collectors.models import RawContentItem, generate_item_id

logger = logging.getLogger(__name__)

DEFAULT_SUBREDDITS = ["technology", "productivity", "todayilearned"]
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ContentPipeline/1.0"


class RedditCollector(BaseCollector):
    """Fetches top daily posts from public subreddits via JSON endpoint."""

    def __init__(self, name: str = "reddit", config: dict[str, Any] | None = None) -> None:
        super().__init__(name, config)
        self.subreddits = self.config.get("subreddits") or DEFAULT_SUBREDDITS
        self.limit_per_sub = self.config.get("limit_per_sub", 10)
        self.timeout = self.config.get("timeout", 10)

    def collect(self, limit: int = 20) -> list[RawContentItem]:
        """Fetch posts across configured subreddits."""
        all_items: list[RawContentItem] = []
        headers = {"User-Agent": USER_AGENT}

        for sub in self.subreddits:
            clean_sub = sub.strip().replace("r/", "")
            url = f"https://www.reddit.com/r/{clean_sub}/top.json?t=day&limit={min(limit, self.limit_per_sub)}"
            logger.info("Fetching Reddit: r/%s", clean_sub)

            try:
                resp = requests.get(url, headers=headers, timeout=self.timeout)
                if resp.status_code != 200:
                    logger.warning("Reddit r/%s returned status %d", clean_sub, resp.status_code)
                    continue

                data = resp.json()
                children = data.get("data", {}).get("children", [])

                for child in children:
                    post = child.get("data", {})
                    title = post.get("title", "").strip()
                    if not title or post.get("stickied"):
                        continue

                    selftext = post.get("selftext", "").strip()
                    permalink = post.get("permalink", "")
                    post_url = f"https://www.reddit.com{permalink}" if permalink else post.get("url", "")
                    score = float(post.get("score", 0))
                    num_comments = int(post.get("num_comments", 0))
                    # Weighted engagement score
                    engagement = score + (num_comments * 2.0)

                    item_id = generate_item_id(f"r/{clean_sub}", post_url, title)
                    all_items.append(
                        RawContentItem(
                            id=item_id,
                            source_name=f"r/{clean_sub}",
                            source_type="reddit",
                            title=title,
                            url=post_url,
                            content=selftext or title,
                            author=post.get("author"),
                            score=engagement,
                            tags=[clean_sub],
                            raw_metadata={
                                "upvotes": score,
                                "comments": num_comments,
                                "domain": post.get("domain", ""),
                            },
                        )
                    )

                logger.info("Collected %d posts from r/%s", len(children), clean_sub)
            except Exception as exc:
                logger.warning("Failed to collect from Reddit r/%s: %s", clean_sub, exc)

        return all_items