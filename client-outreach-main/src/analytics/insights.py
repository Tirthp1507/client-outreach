"""Performance correlation analysis and interpretable recommendation engine.

Phase 9 "Intelligence" layer: identifies relationships between performance and
content decisions (topic pattern, format, hook, audience, duration, scene
structure, CTA, platform), translates snapshot history into human-readable
recommendations, and exposes additive feedback multipliers that ranking and
strategy systems can consume without replacing the existing deterministic
systems.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from analytics.models import (
    InsightFinding,
    InsightsReport,
    MetricAggregate,
    PerformanceSnapshot,
)
from db.models import JobRecord

if TYPE_CHECKING:
    from db.database import Database

logger = logging.getLogger(__name__)

DEFAULT_MIN_SAMPLES = 3
DEFAULT_MIN_JOBS = 2
DEFAULT_MIN_EFFECT = 0.10
DEFAULT_MAX_POINTS = 10.0
DEFAULT_LO_MULTIPLIER = 0.6
DEFAULT_HI_MULTIPLIER = 1.5

# Dimensions that the intelligence engine correlates against content strategy.
DIMENSIONS = [
    "content_format",
    "hook_strategy",
    "target_audience",
    "topic_pattern",
    "scene_count",
    "target_duration",
    "cta_strategy",
    "quality_band",
    "platform",
]

DIMENSION_LABELS = {
    "content_format": "Content Format",
    "hook_strategy": "Hook Strategy",
    "target_audience": "Target Audience",
    "topic_pattern": "Topic Pattern",
    "scene_count": "Scene Structure",
    "target_duration": "Target Duration",
    "cta_strategy": "CTA Strategy",
    "quality_band": "QA Quality Band",
    "platform": "Platform",
}

# Topic-pattern buckets (local, decoupled from the strategist's keyword sets).
TOPIC_PATTERNS: dict[str, set[str]] = {
    "news": {"settle", "billion", "million", "senate", "lawsuit", "court", "probe", "ban", "claim", "break", "deal", "fed", "investigation"},
    "list": {"top", "reasons", "hacks", "tips", "tools", "ways", "methods", "rules", "steps"},
    "tutorial": {"how", "guide", "tutorial", "build", "create", "fix", "setup", "master"},
    "comparison": {"vs", "versus", "better", "compare", "difference", "against"},
    "story": {"history", "origin", "founded", "truth", "behind", "secret", "rise", "fall"},
}


class PerformanceInsightsEngine:
    """Analyzes JobRecord + PerformanceSnapshot history for actionable performance signals."""

    def __init__(self, db: Any | None = None, config: dict[str, Any] | None = None) -> None:
        if db is None:
            from db.database import Database
            self.db = Database()
        else:
            self.db = db
        self.config = config or {}
        ana_cfg = self.config.get("analytics", {}) or {}
        self.min_samples = int(ana_cfg.get("min_samples", DEFAULT_MIN_SAMPLES))
        self.min_jobs = int(ana_cfg.get("min_jobs", DEFAULT_MIN_JOBS))
        self.min_effect = float(ana_cfg.get("min_effect", DEFAULT_MIN_EFFECT))
        self.max_points = float(ana_cfg.get("max_score_adjustment", DEFAULT_MAX_POINTS))

    # -- data scope ---------------------------------------------------------

    def _scope(
        self, platform: str | None = None
    ) -> tuple[list[PerformanceSnapshot], dict[str, JobRecord]]:
        snapshots = self.db.list_snapshots(platform=platform, limit=2000)
        jobs = {j.id: j for j in self.db.list_jobs(limit=500)}
        return snapshots, jobs

    # -- category derivation ------------------------------------------------

    def _category(self, job: JobRecord | None, snapshot: PerformanceSnapshot, dimension: str) -> str | None:
        if dimension == "platform":
            return snapshot.platform
        if job is None:
            return None
        strat = self._strategy_json(job)
        if dimension == "content_format":
            return job.content_format or strat.get("content_format") or "explainer"
        if dimension == "hook_strategy":
            return job.hook_strategy or strat.get("hook_strategy") or "curiosity_gap"
        if dimension == "target_audience":
            return job.target_audience or strat.get("target_audience") or "general_consumers"
        if dimension == "topic_pattern":
            return self.classify_topic_pattern(job.topic)
        if dimension == "scene_count":
            count = strat.get("scene_count")
            return self.bucket_scenes(int(count)) if count else None
        if dimension == "target_duration":
            seconds = strat.get("target_duration_seconds")
            return self.bucket_duration(int(seconds)) if seconds else None
        if dimension == "cta_strategy":
            cta = strat.get("cta_strategy")
            return self.classify_cta(cta) if cta else None
        if dimension == "quality_band":
            return self.bucket_quality(job.quality_score)
        return None

    @staticmethod
    def _strategy_json(job: JobRecord) -> dict[str, Any]:
        try:
            raw = json.loads(job.strategy_json or "{}")
            return raw if isinstance(raw, dict) else {}
        except Exception:
            return {}

    # -- aggregation --------------------------------------------------------

    def aggregate_dimension(
        self, dimension: str, *, platform: str | None = None
    ) -> list[MetricAggregate]:
        """Return per-category performance aggregates for one dimension."""
        snapshots, jobs = self._scope(platform=platform)
        groups: dict[str, list[PerformanceSnapshot]] = defaultdict(list)
        for s in snapshots:
            cat = self._category(jobs.get(s.job_id), s, dimension)
            if not cat:
                continue
            groups[cat].append(s)

        rows: list[MetricAggregate] = []
        for cat, snaps in groups.items():
            count = len(snaps)
            total_views = sum(x.metrics.views for x in snaps)
            rows.append(
                MetricAggregate(
                    dimension=dimension,
                    category=cat,
                    count=count,
                    total_views=total_views,
                    avg_views=round(total_views / count, 1),
                    avg_retention_rate=round(
                        sum(x.metrics.retention_rate_pct for x in snaps) / count, 1
                    ),
                    avg_engagement_score=round(
                        sum(x.engagement_score for x in snaps) / count, 2
                    ),
                )
            )
        rows.sort(key=lambda r: r.avg_engagement_score, reverse=True)
        return rows

    def _benchmark_engagement(self, platform: str | None = None) -> float:
        snapshots, _ = self._scope(platform=platform)
        if not snapshots:
            return 0.0
        return sum(s.engagement_score for s in snapshots) / len(snapshots)

    def _category_job_sets(
        self, dimension: str, platform: str | None = None
    ) -> dict[str, set[str]]:
        """Map each category of a dimension to the set of distinct jobs backing it.

        This powers the *distinct-job* guardrail: a signal is only credible when
        it is observed across multiple unrelated jobs, not a single hot (or cold)
        video producing several snapshots.
        """
        snapshots, jobs = self._scope(platform=platform)
        groups: dict[str, set[str]] = defaultdict(set)
        for s in snapshots:
            cat = self._category(jobs.get(s.job_id), s, dimension)
            if not cat:
                continue
            groups[cat].add(s.job_id)
        return dict(groups)

    # -- interpretable insights ---------------------------------------------

    def generate_insights(
        self,
        *,
        platform: str | None = None,
        min_samples: int | None = None,
        min_jobs: int | None = None,
    ) -> InsightsReport:
        """Correlate each strategic dimension against performance and build recommendations."""
        min_samples = min_samples or self.min_samples
        min_jobs = min_jobs or self.min_jobs
        snapshots, jobs = self._scope(platform=platform)
        report = InsightsReport(total_jobs=len(jobs), total_snapshots=len(snapshots))
        if not snapshots:
            return report

        benchmark = self._benchmark_engagement(platform=platform)
        safe_benchmark = benchmark if benchmark > 0 else 1e-9

        for dim in DIMENSIONS:
            job_sets = self._category_job_sets(dim, platform=platform)
            report.dimensions.append(dim)
            for row in self.aggregate_dimension(dim, platform=platform):
                ratio = row.avg_engagement_score / safe_benchmark
                direction = (
                    "above" if ratio >= 1.05 else "below" if ratio <= 0.95 else "in_line"
                )
                distinct = len(job_sets.get(row.category, set()))
                reliable = row.count >= min_samples and distinct >= min_jobs
                confidence = round(min(1.0, row.count / float(min_samples)), 2)
                report.findings.append(
                    InsightFinding(
                        dimension=dim,
                        category=row.category,
                        count=row.count,
                        avg_engagement_score=row.avg_engagement_score,
                        avg_retention_pct=row.avg_retention_rate,
                        avg_views=row.avg_views,
                        benchmark_engagement=round(benchmark, 2),
                        performance_ratio=round(ratio, 2),
                        direction=direction,
                        confidence=confidence,
                        reliable=reliable,
                        recommendation=self.recommendation_for(
                            dim,
                            row.category,
                            row.avg_engagement_score,
                            benchmark,
                            ratio,
                            row.count,
                            reliable,
                        ),
                    )
                )

        actionable = [
            f
            for f in report.findings
            if f.reliable and f.direction in ("above", "below")
        ]
        actionable.sort(key=lambda f: abs(f.performance_ratio - 1.0), reverse=True)

        seen: set[str] = set()
        for f in actionable:
            key = f"{f.dimension}:{f.category}"
            if key in seen:
                continue
            seen.add(key)
            report.top_recommendations.append(f.recommendation)
            if len(report.top_recommendations) >= 6:
                break

        return report

    @staticmethod
    def recommendation_for(
        dimension: str,
        category: str,
        avg: float,
        benchmark: float,
        ratio: float,
        count: int,
        reliable: bool,
    ) -> str:
        label = DIMENSION_LABELS.get(dimension, dimension)
        scope = f"across {count} snapshot(s)"
        trust = "" if reliable else " (limited sample) "
        if ratio >= 1.05:
            return (
                f"Prefer {category!r} for {label}: it runs {ratio:.2f}x the global "
                f"engagement score ({avg:.1f} vs {benchmark:.1f}){trust}{scope}."
            )
        if ratio <= 0.95:
            return (
                f"Avoid or rework {category!r} for {label}: it trails the global "
                f"average ({ratio:.2f}x, {avg:.1f} vs {benchmark:.1f}){trust}{scope}."
            )
        return (
            f"{category!r} for {label} is in line with the global average "
            f"({ratio:.2f}x){trust}{scope}."
        )

    # -- feedback multipliers -----------------------------------------------

    def get_feedback_multipliers(
        self,
        *,
        platform: str | None = None,
        min_samples: int | None = None,
        min_jobs: int | None = None,
        min_effect: float | None = None,
        lo: float = DEFAULT_LO_MULTIPLIER,
        hi: float = DEFAULT_HI_MULTIPLIER,
    ) -> dict[str, dict[str, float]]:
        """Return per-dimension, per-category multipliers in [lo, hi].

        Strict statistical guardrails (Phase 10): a category only receives a
        non-neutral multiplier when ALL of the following hold, otherwise it
        stays at 1.0 (no-op) so no signal is manufactured from weak data:

        - at least ``min_samples`` snapshots,
        - snapshots come from at least ``min_jobs`` distinct jobs,
        - the ratio deviates from the benchmark by at least ``min_effect``.
        """
        min_samples = min_samples or self.min_samples
        min_jobs = min_jobs or self.min_jobs
        min_effect = float(min_effect) if min_effect is not None else self.min_effect
        benchmark = self._benchmark_engagement(platform=platform)
        if benchmark <= 0:
            return {dim: {} for dim in DIMENSIONS}

        multipliers: dict[str, dict[str, float]] = {}
        for dim in DIMENSIONS:
            job_sets = self._category_job_sets(dim, platform=platform)
            mapping: dict[str, float] = defaultdict(lambda: 1.0)
            for row in self.aggregate_dimension(dim, platform=platform):
                ratio = row.avg_engagement_score / benchmark
                effect = abs(ratio - 1.0)
                if (
                    row.count < min_samples
                    or len(job_sets.get(row.category, set())) < min_jobs
                    or effect < min_effect
                ):
                    mapping[row.category] = 1.0
                    continue
                mapping[row.category] = round(max(lo, min(hi, ratio)), 2)
            multipliers[dim] = dict(mapping)
        return multipliers

    def best_feedback_boost(
        self,
        categories: dict[str, str],
        *,
        min_samples: int | None = None,
        max_points: float | None = None,
        min_jobs: int | None = None,
        min_effect: float | None = None,
    ) -> tuple[float, list[str]]:
        """Compute an additive score shift from the single strongest signal.

        Returns ``(boost_points, explanations)``. A zero boost means the data
        had no reliable signal for any provided category.
        """
        multipliers = self.get_feedback_multipliers(
            min_samples=min_samples, min_jobs=min_jobs, min_effect=min_effect
        )
        max_points = float(max_points) if max_points is not None else self.max_points
        best_delta = 0.0
        best_reasons: list[str] = []
        for dim, cat in categories.items():
            m = multipliers.get(dim, {}).get(cat, 1.0)
            if m == 1.0:
                continue
            delta = (m - 1.0) * max_points
            if abs(delta) > abs(best_delta):
                best_delta = delta
                label = DIMENSION_LABELS.get(dim, dim)
                if m > 1.0:
                    best_reasons = [
                        f"{label} '{cat}' outperforms the global average (multiplier {m:.2f})"
                    ]
                else:
                    best_reasons = [
                        f"{label} '{cat}' underperforms the global average (multiplier {m:.2f})"
                    ]
        return round(best_delta, 1), best_reasons

    def combined_feedback_boost(
        self,
        categories: dict[str, str],
        *,
        min_samples: int | None = None,
        max_points: float | None = None,
        min_jobs: int | None = None,
        min_effect: float | None = None,
    ) -> tuple[float, list[str]]:
        """Opt-in multi-dimension boost (alternative scoring mode).

        Sums only the reliable deltas whose sign agrees with the strongest
        signal (so contradictory dimensions never cancel each other into a
        false neutral), capped at +/- ``max_points``. Default Phase 9 compatibility
        mode remains :meth:`best_feedback_boost`.
        """
        multipliers = self.get_feedback_multipliers(
            min_samples=min_samples, min_jobs=min_jobs, min_effect=min_effect
        )
        max_points = float(max_points) if max_points is not None else self.max_points

        deltas: list[tuple[float, str]] = []
        for dim, cat in categories.items():
            m = multipliers.get(dim, {}).get(cat, 1.0)
            if m == 1.0:
                continue
            deltas.append((round((m - 1.0) * max_points, 1), dim, cat, m))
        if not deltas:
            return 0.0, []

        deltas.sort(key=lambda t: abs(t[0]), reverse=True)
        primary_delta, primary_dim, primary_cat, primary_m = deltas[0]
        sign = 1.0 if primary_delta >= 0 else -1.0

        total = 0.0
        reasons: list[str] = []
        for delta, dim, cat, m in deltas:
            if delta != 0.0 and (delta * sign) >= 0.0:
                total += delta
                label = DIMENSION_LABELS.get(dim, dim)
                if m > 1.0:
                    reasons.append(f"{label} '{cat}' outperforms average (x{m:.2f})")
                else:
                    reasons.append(f"{label} '{cat}' underperforms average (x{m:.2f})")

        total = max(-max_points, min(max_points, total))
        return round(total, 1), reasons[:4]

    # -- category bucketing helpers -----------------------------------------

    @staticmethod
    def classify_topic_pattern(title: str) -> str:
        words = set(re.findall(r"\b\w+\b", (title or "").lower()))
        for pattern, keywords in TOPIC_PATTERNS.items():
            if words & keywords:
                return pattern
        return "general"

    @staticmethod
    def bucket_scenes(count: int) -> str:
        if count <= 2:
            return "1_2_scenes"
        if count == 3:
            return "3_scenes"
        if count == 4:
            return "4_scenes"
        return "5_plus_scenes"

    @staticmethod
    def bucket_duration(seconds: int) -> str:
        if seconds < 30:
            return "under_30s"
        if seconds < 40:
            return "30_39s"
        if seconds < 50:
            return "40_49s"
        return "50_plus_s"

    @staticmethod
    def bucket_quality(score: float) -> str:
        """Bucket a QA/quality score (0-100) for the quality_band dimension."""
        if score < 70:
            return "0_69"
        if score < 80:
            return "70_79"
        if score < 90:
            return "80_89"
        return "90_plus"

    @staticmethod
    def classify_cta(text: str) -> str:
        t = (text or "").lower()
        if any(k in t for k in ("save", "bookmark", "for later")):
            return "save"
        if "share" in t:
            return "share"
        if "follow" in t:
            return "follow"
        if any(k in t for k in ("comment", "your take", "thoughts", "drop")):
            return "discussion"
        return "generic"