"""Data models for social performance metrics, historical snapshots, and analytics aggregation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class PlatformMetrics(BaseModel):
    """Normalized metrics across YouTube Shorts and Instagram Reels."""

    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    watch_time_seconds: float = 0.0
    avg_view_duration_seconds: float = 0.0
    retention_rate_pct: float = 0.0
    impressions: int = 0
    ctr_pct: float = 0.0
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate percentage (likes + comments + shares) / views."""
        if self.views <= 0:
            return 0.0
        return ((self.likes + self.comments + self.shares) / self.views) * 100.0

    @property
    def engagement_score(self) -> float:
        """Composite engagement score weighted by views, retention, and social interactions."""
        if self.views <= 0:
            return 0.0
        # Formula: log-scaled views + retention weight + interaction weight
        base_score = min(50.0, self.views / 100.0)
        retention_score = min(30.0, self.retention_rate_pct * 0.3)
        interaction_score = min(20.0, self.engagement_rate * 2.0)
        return round(base_score + retention_score + interaction_score, 2)


class PerformanceSnapshot(BaseModel):
    """A point-in-time metrics snapshot for a published video."""

    id: str
    job_id: str
    slug: str
    platform: str
    post_id: str | None = None
    metrics: PlatformMetrics = Field(default_factory=PlatformMetrics)
    engagement_score: float = 0.0
    snapshot_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_response: dict[str, Any] = Field(default_factory=dict)


class FormatPerformance(BaseModel):
    """Aggregated performance metrics grouped by content format or hook type."""

    category: str
    count: int = 0
    total_views: int = 0
    avg_views: float = 0.0
    avg_retention_rate: float = 0.0
    avg_engagement_score: float = 0.0


class AnalyticsSummaryReport(BaseModel):
    """System-wide performance analytics report."""

    total_published_jobs: int = 0
    total_snapshots: int = 0
    total_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    total_shares: int = 0
    avg_engagement_score: float = 0.0
    avg_retention_pct: float = 0.0
    by_format: list[FormatPerformance] = Field(default_factory=list)
    by_hook_type: list[FormatPerformance] = Field(default_factory=list)
    by_platform: dict[str, int] = Field(default_factory=dict)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MetricAggregate(FormatPerformance):
    """Aggregated performance for one category of an arbitrary dimension."""

    dimension: str = ""


class InsightFinding(BaseModel):
    """A single interpretable correlation insight between a content decision and performance."""

    dimension: str
    category: str
    count: int = 0
    avg_engagement_score: float = 0.0
    avg_retention_pct: float = 0.0
    avg_views: float = 0.0
    benchmark_engagement: float = 0.0
    performance_ratio: float = 1.0
    direction: str = "in_line"  # "above" | "below" | "in_line"
    confidence: float = 0.0
    reliable: bool = False
    recommendation: str = ""


class InsightsReport(BaseModel):
    """Full correlation analysis report with interpretable recommendations."""

    total_jobs: int = 0
    total_snapshots: int = 0
    dimensions: list[str] = Field(default_factory=list)
    findings: list[InsightFinding] = Field(default_factory=list)
    top_recommendations: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())