"""Performance analytics, historical metrics tracking, and feedback loop infrastructure."""

from analytics.collector import AnalyticsCollector
from analytics.diversity import DiversityScorer
from analytics.factory import SelectionLedger, SelectionScorer, build_selection_scorer
from analytics.feedback import PerformanceFeedbackScorer
from analytics.insights import PerformanceInsightsEngine
from analytics.models import (
    AnalyticsSummaryReport,
    FormatPerformance,
    InsightFinding,
    InsightsReport,
    MetricAggregate,
    PerformanceSnapshot,
    PlatformMetrics,
)
from analytics.reporter import AnalyticsReporter

__all__ = [
    "AnalyticsCollector",
    "AnalyticsReporter",
    "AnalyticsSummaryReport",
    "DiversityScorer",
    "FormatPerformance",
    "InsightFinding",
    "InsightsReport",
    "MetricAggregate",
    "PerformanceFeedbackScorer",
    "PerformanceInsightsEngine",
    "PerformanceSnapshot",
    "PlatformMetrics",
    "SelectionLedger",
    "SelectionScorer",
    "build_selection_scorer",
]