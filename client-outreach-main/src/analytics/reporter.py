"""Analytics reporting and performance aggregation engine."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from analytics.models import (
    AnalyticsSummaryReport,
    FormatPerformance,
    PerformanceSnapshot,
)
from db.models import JobRecord

if TYPE_CHECKING:
    from db.database import Database

logger = logging.getLogger(__name__)


class AnalyticsReporter:
    """Aggregates metrics snapshots into actionable reports and strategy weights."""

    def __init__(self, db: Any | None = None) -> None:
        if db is None:
            from db.database import Database
            self.db = Database()
        else:
            self.db = db


    def generate_summary_report(
        self,
        *,
        platform: str | None = None,
        limit_snapshots: int = 500,
    ) -> AnalyticsSummaryReport:
        """Aggregate snapshot metrics across all jobs and format categories."""
        snapshots = self.db.list_snapshots(platform=platform, limit=limit_snapshots)
        jobs = {j.id: j for j in self.db.list_jobs(limit=200)}

        if not snapshots:
            return AnalyticsSummaryReport(total_published_jobs=len(jobs))

        total_views = sum(s.metrics.views for s in snapshots)
        total_likes = sum(s.metrics.likes for s in snapshots)
        total_comments = sum(s.metrics.comments for s in snapshots)
        total_shares = sum(s.metrics.shares for s in snapshots)
        avg_score = sum(s.engagement_score for s in snapshots) / len(snapshots)
        avg_retention = sum(s.metrics.retention_rate_pct for s in snapshots) / len(snapshots)

        # Group by platform
        by_platform: dict[str, int] = defaultdict(int)
        for s in snapshots:
            by_platform[s.platform] += s.metrics.views

        # Group by format
        format_groups: dict[str, list[PerformanceSnapshot]] = defaultdict(list)
        hook_groups: dict[str, list[PerformanceSnapshot]] = defaultdict(list)

        for s in snapshots:
            job = jobs.get(s.job_id)
            fmt = job.content_format if job else "explainer"
            hook = job.hook_strategy if job else "curiosity_gap"
            format_groups[fmt].append(s)
            hook_groups[hook].append(s)

        by_format = [
            self._aggregate_group(fmt, snaps)
            for fmt, snaps in format_groups.items()
        ]
        by_format.sort(key=lambda x: x.avg_engagement_score, reverse=True)

        by_hook = [
            self._aggregate_group(hk, snaps)
            for hk, snaps in hook_groups.items()
        ]
        by_hook.sort(key=lambda x: x.avg_engagement_score, reverse=True)

        return AnalyticsSummaryReport(
            total_published_jobs=len(jobs),
            total_snapshots=len(snapshots),
            total_views=total_views,
            total_likes=total_likes,
            total_comments=total_comments,
            total_shares=total_shares,
            avg_engagement_score=round(avg_score, 2),
            avg_retention_pct=round(avg_retention, 2),
            by_format=by_format,
            by_hook_type=by_hook,
            by_platform=dict(by_platform),
        )

    def get_format_performance_weights(self) -> dict[str, float]:
        """Return normalized performance multipliers (0.5 to 1.5) by content format for AI Strategist feedback."""
        report = self.generate_summary_report()
        if not report.by_format or report.total_views == 0:
            return {"news": 1.0, "list": 1.0, "tutorial": 1.0, "explainer": 1.0, "comparison": 1.0}

        avg_global = report.avg_engagement_score or 1.0
        weights: dict[str, float] = {}
        for f in report.by_format:
            # Multiplier around 1.0 clamped between 0.6 and 1.5
            ratio = f.avg_engagement_score / avg_global if avg_global > 0 else 1.0
            weights[f.category] = round(max(0.6, min(1.5, ratio)), 2)

        return weights

    def get_hook_performance_weights(self) -> dict[str, float]:
        """Return normalized performance multipliers (0.5 to 1.5) by hook type for AI Strategist feedback."""
        report = self.generate_summary_report()
        if not report.by_hook_type or report.total_views == 0:
            return {
                "statistic_shock": 1.0,
                "curiosity_gap": 1.0,
                "contrarian_bold": 1.0,
                "problem_agitation": 1.0,
                "direct_question": 1.0,
                "story_in_medias_res": 1.0,
            }

        avg_global = report.avg_engagement_score or 1.0
        weights: dict[str, float] = {}
        for h in report.by_hook_type:
            ratio = h.avg_engagement_score / avg_global if avg_global > 0 else 1.0
            weights[h.category] = round(max(0.6, min(1.5, ratio)), 2)

        return weights

    @staticmethod
    def _aggregate_group(category: str, snapshots: list[PerformanceSnapshot]) -> FormatPerformance:
        count = len(snapshots)
        total_views = sum(s.metrics.views for s in snapshots)
        avg_views = total_views / count if count > 0 else 0.0
        avg_retention = sum(s.metrics.retention_rate_pct for s in snapshots) / count if count > 0 else 0.0
        avg_score = sum(s.engagement_score for s in snapshots) / count if count > 0 else 0.0

        return FormatPerformance(
            category=category,
            count=count,
            total_views=total_views,
            avg_views=round(avg_views, 1),
            avg_retention_rate=round(avg_retention, 1),
            avg_engagement_score=round(avg_score, 2),
        )