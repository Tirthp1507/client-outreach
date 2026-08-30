"""SQLite database models for job tracking, strategy decisions, and production publishing."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    QA = "qa"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    STAGED = "staged"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class PublishStatus(str, Enum):
    NOT_STARTED = "not_started"
    STAGED = "staged"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class JobRecord(BaseModel):
    """Represents a complete content generation job with strategy and publishing lifecycle."""

    id: str
    slug: str
    topic: str
    candidate_id: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    status: JobStatus = JobStatus.PENDING_REVIEW
    score: float = 0.0
    quality_score: float = 0.0
    quality_passed: bool = True
    content_format: str = "explainer"
    hook_strategy: str = "curiosity_gap"
    target_audience: str = "general_consumers"
    strategy_json: str = "{}"
    script_json: str = "{}"
    youtube_title: str = ""
    youtube_description: str = ""
    youtube_tags: str = "[]"
    instagram_caption: str = ""
    video_path: str | None = None
    thumbnail_path: str | None = None
    audio_path: str | None = None
    notes: str | None = None
    
    # Phase 7: Production Publishing fields
    publish_status: PublishStatus = PublishStatus.NOT_STARTED
    published_platform: str | None = None
    platform_post_id: str | None = None
    platform_url: str | None = None
    published_at: str | None = None
    publish_attempts: int = 0
    last_publish_error: str | None = None
    publish_response_json: str = "{}"

    # Phase 9: Performance Analytics fields
    latest_views: int = 0
    latest_likes: int = 0
    latest_engagement_score: float = 0.0
    metrics_updated_at: str | None = None

    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reviewed_at: str | None = None


    @property
    def parsed_script(self) -> dict[str, Any]:
        try:
            return json.loads(self.script_json)
        except Exception:
            return {}

    @property
    def parsed_strategy(self) -> dict[str, Any]:
        try:
            return json.loads(self.strategy_json)
        except Exception:
            return {}

    @property
    def parsed_publish_response(self) -> dict[str, Any]:
        try:
            return json.loads(self.publish_response_json)
        except Exception:
            return {}

    @property
    def parsed_tags(self) -> list[str]:
        try:
            return json.loads(self.youtube_tags)
        except Exception:
            return []


class AuditLogRecord(BaseModel):
    """Execution audit trail for recurring scheduled cycles or manual runs."""

    id: str
    cycle_type: str = "scheduled_cycle"
    started_at: str
    completed_at: str
    duration_seconds: float = 0.0
    items_collected: int = 0
    candidates_processed: int = 0
    jobs_generated: int = 0
    qa_passed_count: int = 0
    qa_failed_count: int = 0
    published_count: int = 0
    errors_count: int = 0
    status: str = "success"  # "success" | "partial" | "failed"
    details_json: str = "{}"

    @property
    def parsed_details(self) -> dict[str, Any]:
        try:
            return json.loads(self.details_json)
        except Exception:
            return {}


# Re-export B2B Domain Models
from b2b.models import (
    ApprovalStatus,
    BusinessRecord,
    BusinessResearch,
    BusinessStatus,
    ClaimType,
    DemoRecord,
    DemoStatus,
    DemoType,
    EvidenceCategory,
    OpportunityPriority,
    OpportunityRecord,
    OpportunityType,
    OutreachRecord,
    OutreachResponse,
    QualificationStatus,
    ReplyStatus,
    ResearchEvidence,
    ResponseClassification,
    SendStatus,
    SourceType,
    VerticalType,
)