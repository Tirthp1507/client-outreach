"""Instagram Reels publisher interface with staged/dry-run safety guards."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT
from db.models import JobRecord
from publishers.base import BasePublisher, PublishResult

logger = logging.getLogger(__name__)


class InstagramPublisher(BasePublisher):
    name = "instagram"

    def __init__(self, config: dict[str, Any] | None = None, *, live: bool = False) -> None:
        super().__init__(config, live=live)
        ig_cfg = (self.config.get("publishers", {}) or {}).get("instagram", {})
        self.access_token = ig_cfg.get("access_token", os.environ.get("INSTAGRAM_ACCESS_TOKEN"))
        self.instagram_account_id = ig_cfg.get(
            "account_id", os.environ.get("INSTAGRAM_ACCOUNT_ID")
        )
        self.api_version = ig_cfg.get("api_version", "v19.0")

    def validate_credentials(self) -> bool:
        """Return True if Instagram account ID and access token are configured."""
        return bool(self.access_token and self.instagram_account_id)

    def validate_metadata(self, job: JobRecord) -> tuple[bool, str]:
        caption = job.instagram_caption or job.topic
        if not caption.strip():
            return False, "Instagram caption cannot be empty"
        if len(caption) > 2200:
            return False, f"Instagram caption exceeds 2200 characters ({len(caption)} chars)"
        return True, "Metadata validation passed"

    def publish(self, job: JobRecord, dry_run: bool = False) -> PublishResult:
        """Stage, dry-run, or publish short video to Instagram Reels."""
        # 1. Media validation
        media_ok, media_msg = self.validate_media(job)
        if not media_ok:
            return PublishResult(
                platform=self.name,
                status="failed",
                error=media_msg,
                message=media_msg,
            )

        # 2. Metadata validation
        meta_ok, meta_msg = self.validate_metadata(job)
        if not meta_ok:
            return PublishResult(
                platform=self.name,
                status="failed",
                error=meta_msg,
                message=meta_msg,
            )

        caption = job.instagram_caption or f"⚡ {job.topic}\n\nFollow for more daily updates!"

        upload_payload = {
            "media_type": "REELS",
            "caption": caption,
            "video_path": str(Path(job.video_path).resolve()) if job.video_path else None,
            "thumb_offset": 1500,  # 1.5s
            "account_id": self.instagram_account_id or "MOCK_ACCOUNT_ID",
        }

        staged_dir = PROJECT_ROOT / "output" / "publish_staged"
        staged_dir.mkdir(parents=True, exist_ok=True)
        payload_file = staged_dir / f"instagram_{job.slug}.json"
        payload_file.write_text(json.dumps(upload_payload, indent=2), encoding="utf-8")

        # 3. Dry-run or staged mode (safe default)
        if dry_run or not self.live:
            mode_desc = "Dry-run verified" if dry_run else "Staged"
            logger.info("Instagram %s -> %s", mode_desc, payload_file)
            return PublishResult(
                platform=self.name,
                status="published_dry_run" if dry_run else "staged",
                post_id=f"dry_ig_{job.slug}",
                url=f"https://instagram.com/reel/dry_{job.slug}",
                message=f"Instagram Reels upload payload {mode_desc.lower()} (live upload skipped)",
                payload_file=str(payload_file),
                extra={"dry_run": dry_run},
            )

        # 4. Live publishing execution
        if not self.validate_credentials():
            err_msg = "Instagram live publish failed: Missing INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID"
            logger.error(err_msg)
            return PublishResult(
                platform=self.name,
                status="failed",
                error=err_msg,
                message=err_msg,
                payload_file=str(payload_file),
            )

        try:
            logger.info("Executing live Instagram Reels publish for job %s...", job.id)
            return self._execute_live_publish(upload_payload)
        except Exception as exc:
            err_msg = f"Instagram Graph API error: {exc}"
            logger.error("Live Instagram Reels upload failed for job %s: %s", job.id, exc)
            return PublishResult(
                platform=self.name,
                status="failed",
                error=err_msg,
                message=err_msg,
                payload_file=str(payload_file),
            )

    def _execute_live_publish(self, payload: dict[str, Any]) -> PublishResult:
        """Execute Instagram Graph API 2-step container upload and publish."""
        import urllib.parse
        import urllib.request

        account_id = self.instagram_account_id
        token = self.access_token
        caption = payload["caption"]

        # Step 1: Create Container
        create_url = f"https://graph.facebook.com/{self.api_version}/{account_id}/media"
        post_data = urllib.parse.urlencode({
            "media_type": "REELS",
            "caption": caption,
            "access_token": token,
        }).encode("utf-8")

        req = urllib.request.Request(create_url, data=post_data, method="POST")
        with urllib.request.urlopen(req) as resp:
            container_data = json.loads(resp.read().decode("utf-8"))
            container_id = container_data.get("id")
            if not container_id:
                raise RuntimeError(f"Failed to create Instagram container: {container_data}")

        # Step 2: Publish Container
        publish_url = f"https://graph.facebook.com/{self.api_version}/{account_id}/media_publish"
        pub_data = urllib.parse.urlencode({
            "creation_id": container_id,
            "access_token": token,
        }).encode("utf-8")

        pub_req = urllib.request.Request(publish_url, data=pub_data, method="POST")
        with urllib.request.urlopen(pub_req) as pub_resp:
            pub_res = json.loads(pub_resp.read().decode("utf-8"))
            post_id = pub_res.get("id") or container_id
            return PublishResult(
                platform=self.name,
                status="published",
                post_id=post_id,
                url=f"https://instagram.com/reel/{post_id}",
                message="Instagram Reel published successfully",
                extra={"creation_id": container_id, "post_id": post_id},
            )