"""Transparent 0-100 Opportunity Scorer.

Produces an explainable economic score with a per-dimension breakdown,
explicit reasons, and a SEPARATE confidence value. Unknown dimensions are
scored at a conservative midpoint ("insufficient data -> neutral") so the
scorer never manufactures fake precision.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from typing import List, Optional

from b2b.analyst import AnalysisResult
from b2b.models import (
    BusinessRecord,
    BusinessResearch,
    OpportunityPriority,
    OpportunityType,
    QualificationStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class ScoreDimension:
    """One scoring axis: how much it contributes and why."""
    key: str
    label: str
    max_points: float
    points: float
    reason: str


@dataclass
class ScoredOpportunity:
    """A fully scored opportunity, ready to persist as an OpportunityRecord."""
    business_id: str
    opportunity_type: Optional[OpportunityType]
    title: str
    problem_summary: str
    proposed_solution: str
    business_value: str
    score: float
    dimensions: List[ScoreDimension] = dc_field(default_factory=list)
    score_reasons: List[str] = dc_field(default_factory=list)
    risks: List[str] = dc_field(default_factory=list)
    confidence: float = 0.0
    priority: OpportunityPriority = OpportunityPriority.MEDIUM
    qualification_status: QualificationStatus = QualificationStatus.REVIEW_NEEDED
    evidence_ids: List[str] = dc_field(default_factory=list)
    supporting_claims: List[str] = dc_field(default_factory=list)

    @property
    def score_breakdown_text(self) -> str:
        """Human-readable breakdown, e.g. ``Problem severity 19/20: ...``."""
        lines = [f"Opportunity Score: {self.score:.1f}/100"]
        for d in self.dimensions:
            lines.append(f"{d.label:<26} {d.points:.1f}/{d.max_points:.0f}  -  {d.reason}")
        return "\n".join(lines)

    def api_dict(self) -> dict:
        return {
            "business_id": self.business_id,
            "opportunity_type": self.opportunity_type.value if self.opportunity_type else None,
            "title": self.title,
            "problem_summary": self.problem_summary,
            "proposed_solution": self.proposed_solution,
            "business_value": self.business_value,
            "score": round(self.score, 1),
            "score_reasons": self.score_reasons,
            "risks": self.risks,
            "confidence": round(self.confidence, 3),
            "priority": self.priority.value,
            "qualification_status": self.qualification_status.value,
            "evidence_ids": self.evidence_ids,
            "dimensions": [{
                "key": d.key, "label": d.label, "max": d.max_points,
                "points": round(d.points, 1), "reason": d.reason,
            } for d in self.dimensions],
        }


# Dimension budgets (sum to 100).
_BUDGET: List = [
    ("problem_severity", "Problem severity", 20),
    ("evidence_strength", "Evidence strength", 15),
    ("business_fit", "Business fit", 15),
    ("potential_roi", "Potential ROI", 15),
    ("implementation_feasibility", "Implementation fit", 10),
    ("technology_readiness", "Technology readiness", 10),
    ("outreach_relevance", "Outreach relevance", 10),
    ("willingness_to_buy", "Willingness to buy", 5),
]

_NEUTRAL_REASON = "insufficient data - conservative neutral"

# Per-type ROI / severity baselines (evidence nudges them up or down).
_TYPE_PROFILE: dict = {
    OpportunityType.ONLINE_BOOKING: {"problem": 17, "roi": 16},
    OpportunityType.LEAD_CAPTURE: {"problem": 15, "roi": 15},
    OpportunityType.ORDERING_SYSTEM: {"problem": 15, "roi": 14},
    OpportunityType.WEBSITE_MODERNIZATION: {"problem": 13, "roi": 12},
    OpportunityType.CUSTOMER_PORTAL: {"problem": 14, "roi": 12},
    OpportunityType.WHATSAPP_AUTOMATION: {"problem": 13, "roi": 13},
    OpportunityType.CUSTOM_WEBAPP: {"problem": 13, "roi": 11},
}


class OpportunityScorer:
    """Evidence-weighted, dimension-level opportunity scorer."""

    def score(
        self,
        analysis: AnalysisResult,
        business: BusinessRecord,
        research: Optional[BusinessResearch] = None,
    ) -> Optional[ScoredOpportunity]:
        """Score a supported analysis. Returns None for insufficient evidence."""
        if not analysis.sufficient_evidence or analysis.opportunity_type is None:
            return None

        research = research or BusinessResearch(business_id=business.id)

        dims: dict[str, ScoreDimension] = {}
        profile = _TYPE_PROFILE.get(analysis.opportunity_type, {"problem": 13, "roi": 12})

        # 1. Problem severity (0-20)
        sev = profile["problem"]
        reason = f"{analysis.opportunity_type.value.replace('_', ' ')} gap detected for this vertical"
        if not research.website_exists:
            sev = min(20, sev + 2); reason = "no website presence compounds the gap"
        elif research.observed_weaknesses:
            sev = min(20, sev + 1)
        if not research.is_mobile_friendly:
            reason += "; site is not mobile-friendly"
        dims["problem_severity"] = ScoreDimension("problem_severity", "Problem severity", 20, sev, reason)

        # 2. Evidence strength (0-15)
        evs = research.evidence
        verified = sum(1 for e in evs if e.claim_type.value == "verified_fact") if evs else 0
        support_conf = analysis.confidence
        if evs:
            strength = min(15, 4 + 3 * min(verified, 3) + 5 * support_conf)
            reason = f"{verified} verified fact(s), {len(evs)} total evidence, analyst confidence {support_conf:.2f}"
        else:
            strength = 4.0
            reason = "no evidence records stored"
        dims["evidence_strength"] = ScoreDimension("evidence_strength", "Evidence strength", 15, round(strength, 1), reason)

        # 3. Business fit (0-15)
        fit = 9.0
        fit_reason = "category matches a recognised vertical"
        if business.category and business.category.strip().lower() not in ("general_smb", "general", "other"):
            fit = 12.0
            fit_reason = f"'{business.category}' is a well-understood local-services vertical"
        if research.website_exists:
            fit = min(15, fit + 1.5); fit_reason += "; business already has online presence to build on"
        dims["business_fit"] = ScoreDimension("business_fit", "Business fit", 15, fit, fit_reason)

        # 4. Potential ROI (0-15)
        roi = profile["roi"]
        roi_reason = "typed opportunity has a clear revenue/operations payoff"
        if analysis.business_value and analysis.opportunity_type in (
            OpportunityType.ONLINE_BOOKING, OpportunityType.LEAD_CAPTURE, OpportunityType.ORDERING_SYSTEM):
            roi = min(15, roi + 1); roi_reason = "captures missed demand (bookings/leads/orders)"
        if not research.website_exists:
            roi = max(6, roi - 1); roi_reason += "; ground-up build costs must be weighed"
        dims["potential_roi"] = ScoreDimension("potential_roi", "Potential ROI", 15, roi, roi_reason)

        # 5. Implementation feasibility (0-10)
        effort_map = {"low": 9, "medium": 7, "high": 4, "unknown": 6}
        effort = effort_map.get(analysis.implementation_effort, 6)
        if analysis.opportunity_type == OpportunityType.WEBSITE_MODERNIZATION and research.website_exists:
            effort = min(10, effort + 1)
        dims["implementation_feasibility"] = ScoreDimension(
            "implementation_feasibility", "Implementation fit", 10, effort,
            f"estimated effort '{analysis.implementation_effort}'")

        # 6. Technology readiness (0-10)
        ready = 5.0
        ready_reason = _NEUTRAL_REASON
        if research.booking_system_found or research.ordering_system_found:
            ready = 8.5
            ready_reason = "existing digital systems found - can integrate around them"
        elif research.website_exists:
            ready = 6.5
            ready_reason = "a website exists (a digital baseline is present)"
        elif research.website_exists is False:
            ready = 3.0
            ready_reason = "no website - low digital maturity to build from"
        dims["technology_readiness"] = ScoreDimension("technology_readiness", "Technology readiness", 10, ready, ready_reason)

        # 7. Outreach relevance (0-10)
        p = len(analysis.supporting_claims)
        if p == 0:
            outreach = 3.0
            outreach_reason = "no specific claims to personalise outreach on"
        else:
            outreach = min(10, 5 + p * 1.5)
            outreach_reason = f"{p} traceable evidence claim(s) available for personalisation"
        dims["outreach_relevance"] = ScoreDimension("outreach_relevance", "Outreach relevance", 10, round(outreach, 1), outreach_reason)

        # 8. Willingness to buy (0-5) -- genuinely unknowable from public data.
        w2b = 2.5
        w2b_reason = "intent unobservable from public data - neutral midpoint"
        if not research.website_exists:
            w2b = 3.0
            w2b_reason = "no online presence suggests openness (or indifference) - keep neutral"
        dims["willingness_to_buy"] = ScoreDimension("willingness_to_buy", "Willingness to buy", 5, w2b, w2b_reason)

        # Aggregate
        score = sum(d.points for d in dims.values())
        score = max(0.0, min(100.0, score))
        score_rounded = round(score, 1)

        reasons = self._reasons(dims)
        priority = self._priority(score_rounded)
        qualification = self._qualification(score_rounded, analysis.confidence)

        return ScoredOpportunity(
            business_id=business.id,
            opportunity_type=analysis.opportunity_type,
            title=analysis.title or "",
            problem_summary=analysis.problem_summary or "",
            proposed_solution=analysis.proposed_solution or "",
            business_value=analysis.business_value or "",
            score=score_rounded,
            dimensions=list(dims.values()),
            score_reasons=reasons,
            risks=list(analysis.risks),
            confidence=analysis.confidence,
            priority=priority,
            qualification_status=qualification,
            evidence_ids=list(analysis.evidence_ids),
            supporting_claims=list(analysis.supporting_claims),
        )

    @staticmethod
    def _reasons(dims: dict) -> List[str]:
        reasons: List[str] = []
        for d in dims.values():
            share = d.points / d.max_points
            if share >= 0.7:
                reasons.append(f"+ {d.label} {d.points:.1f}/{d.max_points:.1f}: {d.reason}")
            elif share <= 0.4:
                reasons.append(f"- {d.label} {d.points:.1f}/{d.max_points:.1f}: {d.reason}")
        if not reasons:
            reasons.append("= All dimensions clustered near neutral; insufficient signal per dimension.")
        return reasons

    @staticmethod
    def _priority(score: float) -> OpportunityPriority:
        if score >= 80:
            return OpportunityPriority.HIGH
        if score >= 65:
            return OpportunityPriority.MEDIUM
        return OpportunityPriority.LOW

    @staticmethod
    def _qualification(score: float, confidence: float) -> QualificationStatus:
        if score >= 60 and confidence >= 0.4:
            return QualificationStatus.QUALIFIED
        if score < 40 or confidence < 0.25:
            return QualificationStatus.UNQUALIFIED
        return QualificationStatus.REVIEW_NEEDED