"""Abstract publisher interface, validation, and result structures."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from db.models import JobRecord


class PublishResult(BaseModel):
    """Result of staging, dry-running, or executing a social media publish action."""

    platform: str
    status: str  # "staged" | "published" | "published_dry_run" | "failed" | "skipped" | "publishing"
    post_id: str | None = None
    url: str | None = None
    message: str = ""
    payload_file: str | None = None
    error: str | None = None
    attempts: int = 1
    extra: dict[str, Any] = Field(default_factory=dict)


class BasePublisher(ABC):
    """Abstract base class for all social media video publishers."""

    name: str = "base"

    def __init__(self, config: dict[str, Any] | None = None, *, live: bool = False) -> None:
        self.config = config or {}
        # Live publishing requires explicit opt-in (live=True). Default is safe staged/dry-run mode.
        self.live = live

    @abstractmethod
    def validate_credentials(self) -> bool:
        """Return True if credentials for this platform are present and valid."""
        pass

    def validate_media(self, job: JobRecord) -> tuple[bool, str]:
        """Validate media file existence, non-zero size, and video format."""
        if not job.video_path:
            return False, "Job has no video_path recorded"
        vpath = Path(job.video_path)
        if not vpath.exists():
            return False, f"Video file does not exist on disk: {vpath}"
        if vpath.stat().st_size <= 0:
            return False, f"Video file is empty (0 bytes): {vpath}"
        if vpath.suffix.lower() != ".mp4":
            return False, f"Expected MP4 container, got: {vpath.suffix}"
        return True, "Media validation passed"

    @abstractmethod
    def validate_metadata(self, job: JobRecord) -> tuple[bool, str]:
        """Validate required platform title, description/caption, and tag constraints."""
        pass

    @abstractmethod
    def publish(self, job: JobRecord, dry_run: bool = False) -> PublishResult:
        """Publish or stage the job video and metadata to the platform."""
        pass

    def get_status(self, job: JobRecord) -> PublishResult:
        """Check post status on the remote platform or from persistent state."""
        return PublishResult(
            platform=self.name,
            status=job.publish_status.value if hasattr(job.publish_status, "value") else str(job.publish_status),
            post_id=job.platform_post_id,
            url=job.platform_url,
            message=f"Current status: {job.publish_status}",
            attempts=job.publish_attempts,
        )

    def retry(self, job: JobRecord, dry_run: bool = False) -> PublishResult:
        """Re-attempt publishing a previously failed or stalled job."""
        return self.publish(job, dry_run=dry_run)