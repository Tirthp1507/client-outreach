"""YouTube Shorts publisher interface with staged/dry-run safety guards."""

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


class YouTubePublisher(BasePublisher):
    name = "youtube"

    def __init__(self, config: dict[str, Any] | None = None, *, live: bool = False) -> None:
        super().__init__(config, live=live)
        yt_cfg = (self.config.get("publishers", {}) or {}).get("youtube", {})
        self.client_secrets_file = yt_cfg.get(
            "client_secrets_file", os.environ.get("YOUTUBE_CLIENT_SECRETS")
        )
        self.token_file = yt_cfg.get("token_file", os.environ.get("YOUTUBE_TOKEN_FILE"))
        self.access_token = yt_cfg.get("access_token", os.environ.get("YOUTUBE_ACCESS_TOKEN"))
        self.privacy_status = yt_cfg.get("privacy_status", "private")  # default to private

    def validate_credentials(self) -> bool:
        """Validate if OAuth secrets, token file, or access token is configured."""
        if self.access_token:
            return True
        if self.token_file and Path(self.token_file).exists():
            return True
        if self.client_secrets_file and Path(self.client_secrets_file).exists():
            return True
        return False

    def validate_metadata(self, job: JobRecord) -> tuple[bool, str]:
        title = job.youtube_title or job.topic
        if not title.strip():
            return False, "YouTube title cannot be empty"
        if len(title) > 100:
            return False, f"YouTube title exceeds 100 characters ({len(title)} chars)"
        return True, "Metadata validation passed"

    def publish(self, job: JobRecord, dry_run: bool = False) -> PublishResult:
        """Stage, dry-run, or publish short video to YouTube Shorts."""
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

        title = job.youtube_title or f"{job.topic[:58]} #Shorts"
        if "#Shorts" not in title:
            title = f"{title[:58]} #Shorts"

        description = job.youtube_description or f"Breakdown of {job.topic}"
        tags = job.parsed_tags or ["shorts", "tech", "news"]

        upload_payload = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "28",  # Science & Technology
            },
            "status": {
                "privacyStatus": self.privacy_status,
                "selfDeclaredMadeForKids": False,
            },
            "video_path": str(Path(job.video_path).resolve()) if job.video_path else None,
            "thumbnail_path": str(Path(job.thumbnail_path).resolve()) if job.thumbnail_path else None,
        }

        # Staging directory
        staged_dir = PROJECT_ROOT / "output" / "publish_staged"
        staged_dir.mkdir(parents=True, exist_ok=True)
        payload_file = staged_dir / f"youtube_{job.slug}.json"
        payload_file.write_text(json.dumps(upload_payload, indent=2), encoding="utf-8")

        # 3. Dry-run or staged mode (safe default)
        if dry_run or not self.live:
            mode_desc = "Dry-run verified" if dry_run else "Staged"
            logger.info("YouTube %s -> %s (privacy=%s)", mode_desc, payload_file, self.privacy_status)
            return PublishResult(
                platform=self.name,
                status="published_dry_run" if dry_run else "staged",
                post_id=f"dry_yt_{job.slug}",
                url=f"https://youtube.com/shorts/dry_{job.slug}",
                message=f"YouTube Shorts upload payload {mode_desc.lower()} (live upload skipped)",
                payload_file=str(payload_file),
                extra={"privacy": self.privacy_status, "dry_run": dry_run},
            )

        # 4. Live publishing execution
        if not self.validate_credentials():
            err_msg = "YouTube live publish failed: Missing valid OAuth credentials (YOUTUBE_CLIENT_SECRETS / YOUTUBE_ACCESS_TOKEN)"
            logger.error(err_msg)
            return PublishResult(
                platform=self.name,
                status="failed",
                error=err_msg,
                message=err_msg,
                payload_file=str(payload_file),
            )

        try:
            logger.info("Executing live YouTube upload for job %s...", job.id)
            return self._execute_live_upload(upload_payload)
        except Exception as exc:
            err_msg = f"YouTube API upload error: {exc}"
            logger.error("Live YouTube upload failed for job %s: %s", job.id, exc)
            return PublishResult(
                platform=self.name,
                status="failed",
                error=err_msg,
                message=err_msg,
                payload_file=str(payload_file),
            )

    def _execute_live_upload(self, payload: dict[str, Any]) -> PublishResult:
        """Call YouTube Data API v3 upload endpoint."""
        token = self.access_token
        if not token and self.token_file and Path(self.token_file).exists():
            try:
                tok_data = json.loads(Path(self.token_file).read_text(encoding="utf-8"))
                token = tok_data.get("access_token")
            except Exception:
                pass

        if not token:
            raise ValueError("No valid OAuth access token available for YouTube upload")

        video_path = Path(payload["video_path"])
        url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(video_path.stat().st_size),
            "X-Upload-Content-Type": "video/mp4",
        }

        meta_json = json.dumps({
            "snippet": payload["snippet"],
            "status": payload["status"],
        }).encode("utf-8")

        import urllib.request
        req = urllib.request.Request(url, data=meta_json, headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            upload_url = resp.headers.get("Location")
            if not upload_url:
                raise RuntimeError("YouTube API did not return resumable upload Location")

        with open(video_path, "rb") as vf:
            upload_req = urllib.request.Request(
                upload_url,
                data=vf.read(),
                headers={"Content-Type": "video/mp4"},
                method="PUT",
            )
            with urllib.request.urlopen(upload_req) as up_resp:
                res_body = json.loads(up_resp.read().decode("utf-8"))
                vid_id = res_body.get("id")
                return PublishResult(
                    platform=self.name,
                    status="published",
                    post_id=vid_id,
                    url=f"https://youtube.com/shorts/{vid_id}",
                    message="YouTube Short uploaded successfully",
                    extra={"video_id": vid_id},
                )