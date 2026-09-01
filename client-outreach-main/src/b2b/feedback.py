"""Feedback / conversion learning layer for outreach optimization.

Conservative philosophy (same as the Phase 9 analytics guardrails):
insufficient data => neutral. A dimension only produces a recommendation when
it has at least ``min_samples`` observations AND the observed effect size
beats ``min_effect``. Everything is computed from the persisted outreach and
response records - nothing is manufactured.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from typing import Dict, List, Optional

from b2b.models import (
    DemoRecord,
    OpportunityRecord,
    OutreachRecord,
    ResponseClassification,
    SendStatus,
    VerticalType,
)

# NOTE: `db.database.Database` is imported lazily inside methods to avoid the
# db.database <-> b2b.models <-> b2b package init import cycle.

logger = logging.getLogger(__name__)

POSITIVE_CLASSES = {
    ResponseClassification.INTERESTED,
    ResponseClassification.WANTS_MEETING,
    ResponseClassification.WANTS_PRICING,
    ResponseClassification.QUESTION,
}


@dataclass
class OutcomeSample:
    """One observed outreach thread in the feedback ledger."""
    opportunity_type: str
    vertical: str
    demo_type: str
    score_band: str
    sent: bool = True
    replied: bool = False
    positive: bool = False   # replied AND positive signal

    @classmethod
    def from_record(cls, out: OutreachRecord, opp: OpportunityRecord,
                    demo: Optional[DemoRecord], positive: bool) -> "OutcomeSample":
        band = cls._band(opp.score)
        return cls(
            opportunity_type=opp.opportunity_type.value,
            vertical=demo.vertical.value if demo else VerticalType.GENERAL_SMB.value,
            demo_type=demo.demo_type.value if demo else "none",
            score_band=band,
            replied=positive or bool(out.provider_message_id),
            positive=positive,
        )

    @staticmethod
    def _band(score: float) -> str:
        if score >= 80:
            return "80-100"
        if score >= 60:
            return "60-79"
        if score >= 40:
            return "40-59"
        return "0-39"


@dataclass
class DimensionFinding:
    dimension: str
    bucket: str
    n: int
    reply_rate: Optional[float]
    positive_rate: Optional[float]
    delta: Optional[float]     # reply_rate - baseline
    reliable: bool
    recommendation: Optional[str]


@dataclass
class FeedbackReport:
    baseline_reply_rate: Optional[float]
    totals_sent: int
    totals_replied: int
    findings: List[DimensionFinding] = dc_field(default_factory=list)
    neutral_note: str = ""

    def api_dict(self) -> dict:
        return {
            "baseline_reply_rate": self.baseline_reply_rate,
            "totals_sent": self.totals_sent,
            "totals_replied": self.totals_replied,
            "findings": [f.__dict__ for f in self.findings],
            "neutral_note": self.neutral_note,
        }


class OutreachFeedbackEngine:
    """Learns from real outcomes; returns only statistically honest signals."""

    def __init__(self, min_samples: int = 5, min_effect: float = 0.10) -> None:
        self.min_samples = min_samples
        self.min_effect = min_effect

    def learn(self, db: Database) -> FeedbackReport:
        samples, sent, replied = self._collect(db)
        baseline = (replied / sent) if sent else None
        findings = self._findings(samples, baseline)
        note = ""
        if sent < self.min_samples:
            note = (f"Only {sent} sent conversation(s) observed - below the "
                    f"{self.min_samples} sample minimum. No recommendations produced (neutral by design).")
        elif baseline is None:
            note = "No baseline available; findings limited to observations."

        return FeedbackReport(
            baseline_reply_rate=baseline,
            totals_sent=sent,
            totals_replied=replied,
            findings=findings,
            neutral_note=note,
        )

    # -- data collection ---------------------------------------------------
    def _collect(self, db: Database) -> tuple[List[OutcomeSample], int, int]:
        samples: List[OutcomeSample] = []
        sent = 0
        replied = 0
        for out in db.list_outreach(approval_status="all"):
            if out.send_status != SendStatus.SENT:
                continue
            sent += 1
            responses = db.list_outreach_responses(outreach_id=out.id)
            positive = any(r.classification in POSITIVE_CLASSES for r in responses)
            if responses:
                replied += 1
            opp = db.get_opportunity(out.opportunity_id)
            demo = db.get_demo(out.demo_id) if out.demo_id else None
            if opp is None:
                continue
            samples.append(OutcomeSample.from_record(out, opp, demo, positive))
        return samples, sent, replied

    # -- findings ----------------------------------------------------------
    def _findings(self, samples: List[OutcomeSample],
                  baseline: Optional[float]) -> List[DimensionFinding]:
        if not samples or baseline is None:
            return []
        dims = {
            "opportunity_type": lambda s: s.opportunity_type,
            "vertical": lambda s: s.vertical,
            "demo_type": lambda s: s.demo_type,
            "score_band": lambda s: s.score_band,
        }
        findings: List[DimensionFinding] = []
        for dim_name, key_fn in dims.items():
            buckets: Dict[str, List[OutcomeSample]] = {}
            for s in samples:
                buckets.setdefault(key_fn(s), []).append(s)
            for bucket, group in buckets.items():
                n = len(group)
                n_reply = sum(1 for s in group if s.replied)
                rate = n_reply / n if n else None
                delta = round((rate - baseline), 4) if rate is not None else None
                reliable = n >= self.min_samples and delta is not None and abs(delta) >= self.min_effect
                rec = None
                if reliable:
                    direction = "higher" if delta > 0 else "lower"
                    rec = (f"Bucket '{bucket}' in dimension {dim_name} replies at {rate:.0%} "
                           f"({direction} than the {baseline:.0%} baseline, n={n}). "
                           f"Consider weighting {dim_name}='{bucket}' accordingly in future scoring/copy selection.")
                findings.append(DimensionFinding(
                    dimension=dim_name,
                    bucket=bucket,
                    n=n,
                    reply_rate=rate,
                    positive_rate=(sum(1 for s in group if s.positive) / n) if n else None,
                    delta=delta,
                    reliable=reliable,
                    recommendation=rec,
                ))
        findings.sort(key=lambda f: (f.reliable, f.n), reverse=True)
        return findings

    def best_signals(self, report: FeedbackReport) -> List[DimensionFinding]:
        """Only statistically supported recommendations; empty when sparse."""
        return [f for f in report.findings if f.reliable]