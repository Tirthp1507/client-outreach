"""AI Business Analyst: evidence-backed opportunity analysis for SMB outreach.

Turns a verified :class:`BusinessResearch` record into a structured
`AnalysisResult` answering the analyst's core questions:

1. What does this business appear to do?
2. What workflow/problem could be improved?
3. What evidence supports that conclusion?
4. What software/automation solution could we offer?
5. Why would this matter to the business?
6. How difficult would the implementation likely be?
7. How strong is the opportunity?

Non-negotiable rule: if the evidence is insufficient to support an
opportunity hypothesis, the analysis is marked ``sufficient_evidence=False``
and NO opportunity is manufactured. Unknown/missing signals are recorded as
``unknowns`` rather than invented facts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field
from typing import Dict, List, Optional, Sequence, Tuple

from b2b.models import (
    BusinessRecord,
    BusinessResearch,
    ClaimType,
    EvidenceCategory,
    OpportunityType,
    ResearchEvidence,
    VerticalType,
)

logger = logging.getLogger(__name__)

# Vertical -> OpportunityType affinity used to rank candidate gaps.
VERTICAL_BOOKING_APPT = {
    VerticalType.SALON, VerticalType.CLINIC, VerticalType.GYM,
    VerticalType.COACHING, VerticalType.RESTAURANT, VerticalType.HOTEL,
}
VERTICAL_CONSULTATIVE = {
    VerticalType.COACHING, VerticalType.PROFESSIONAL_SERVICES,
    VerticalType.REAL_ESTATE, VerticalType.CLINIC,
}
VERTICAL_ORDERING = {VerticalType.RESTAURANT, VerticalType.HOTEL, VerticalType.RETAIL}

CATEGORY_TO_VERTICAL: Dict[str, VerticalType] = {
    "restaurant": VerticalType.RESTAURANT,
    "food": VerticalType.RESTAURANT,
    "cafe": VerticalType.RESTAURANT,
    "salon": VerticalType.SALON,
    "beauty": VerticalType.SALON,
    "spa": VerticalType.SALON,
    "clinic": VerticalType.CLINIC,
    "medical": VerticalType.CLINIC,
    "dental": VerticalType.CLINIC,
    "doctor": VerticalType.CLINIC,
    "gym": VerticalType.GYM,
    "fitness": VerticalType.GYM,
    "coaching": VerticalType.COACHING,
    "education": VerticalType.COACHING,
    "training": VerticalType.COACHING,
    "classes": VerticalType.COACHING,
    "retail": VerticalType.RETAIL,
    "store": VerticalType.RETAIL,
    "real_estate": VerticalType.REAL_ESTATE,
    "property": VerticalType.REAL_ESTATE,
    "hotel": VerticalType.HOTEL,
    "lodging": VerticalType.HOTEL,
    "automotive": VerticalType.AUTOMOTIVE,
    "car": VerticalType.AUTOMOTIVE,
    "professional_services": VerticalType.PROFESSIONAL_SERVICES,
    "consulting": VerticalType.PROFESSIONAL_SERVICES,
    "services": VerticalType.PROFESSIONAL_SERVICES,
    "general_smb": VerticalType.GENERAL_SMB,
    "general": VerticalType.GENERAL_SMB,
    "other": VerticalType.GENERAL_SMB,
}


def vertical_for(category: str) -> VerticalType:
    """Map a discovery category/industry string onto the VerticalType taxonomy."""
    key = (category or "general_smb").strip().lower()
    return CATEGORY_TO_VERTICAL.get(key, VerticalType.GENERAL_SMB)


@dataclass
class AnalysisResult:
    """Structured opportunity hypothesis derived strictly from evidence.

    * ``sufficient_evidence`` False => the analyst found no hypothesis worth
      manufacturing; callers must NOT create an OpportunityRecord.
    """
    business_id: str
    opportunity_type: Optional[OpportunityType] = None
    title: Optional[str] = None
    problem_summary: Optional[str] = None
    proposed_solution: Optional[str] = None
    business_value: Optional[str] = None
    rationale: str = ""
    confidence: float = 0.0
    implementation_effort: str = "unknown"
    risks: List[str] = dc_field(default_factory=list)
    unknowns: List[str] = dc_field(default_factory=list)
    evidence_ids: List[str] = dc_field(default_factory=list)
    supporting_claims: List[str] = dc_field(default_factory=list)
    reasoning: List[str] = dc_field(default_factory=list)
    insufficient_reason: Optional[str] = None
    sufficient_evidence: bool = False

    def api_dict(self) -> dict:
        """Plain JSON-ready representation for the dashboard/CLI."""
        return {
            "business_id": self.business_id,
            "opportunity_type": self.opportunity_type.value if self.opportunity_type else None,
            "title": self.title,
            "problem_summary": self.problem_summary,
            "proposed_solution": self.proposed_solution,
            "business_value": self.business_value,
            "rationale": self.rationale,
            "confidence": self.confidence,
            "implementation_effort": self.implementation_effort,
            "risks": self.risks,
            "unknowns": self.unknowns,
            "evidence_ids": self.evidence_ids,
            "supporting_claims": self.supporting_claims,
            "reasoning": self.reasoning,
            "insufficient_reason": self.insufficient_reason,
            "sufficient_evidence": self.sufficient_evidence,
        }


# --- Gap detection signals (pure functions over research/evidence) --------

def has_category_type(evidence: Sequence[ResearchEvidence], *cats: EvidenceCategory) -> bool:
    return any(e.category in cats for e in evidence)


class BusinessAnalyst:
    """Deterministic, evidence-gated opportunity analyst.

    Runs on the verified research produced by a research provider. Where no
    research exists yet, analysis is refused rather than guessed.
    """

    def __init__(self) -> None:
        self._multi_opportunity_support = True

    # -- public API ---------------------------------------------------------
    def analyze(
        self,
        business: BusinessRecord,
        research: Optional[BusinessResearch],
    ) -> AnalysisResult:
        """Analyze one business and return a single best-supported hypothesis."""
        if research is None:
            return self._insufficient(business, "No research record for this business; analysis deferred.")
        if not research.evidence and not research.observed_weaknesses:
            return self._insufficient(
                business,
                "No evidence or observed signals recorded; refusing to manufacture an opportunity.",
            )

        vertical = vertical_for(business.category)
        signals = self._collect_signals(research, vertical)

        ranked = self._rank_hypotheses(signals, vertical)
        if not ranked:
            return self._insufficient(
                business,
                "No evidence-backed gap hypothesis could be formed for this business.",
            )

        best_type, support = ranked[0]
        return self._build_result(business, research, vertical, best_type, support)

    def analyze_all(
        self,
        business: BusinessRecord,
        research: Optional[BusinessResearch],
        max_hypotheses: int = 2,
    ) -> List[AnalysisResult]:
        """Return the top (up to ``max_hypotheses``) supported hypotheses."""
        if research is None:
            return [self._insufficient(business, "No research record for this business; analysis deferred.")]
        if not research.evidence and not research.observed_weaknesses:
            return [self._insufficient(business, "No evidence or observed signals recorded.")]

        vertical = vertical_for(business.category)
        signals = self._collect_signals(research, vertical)
        ranked = self._rank_hypotheses(signals, vertical)
        if not ranked:
            return [self._insufficient(business, "No evidence-backed gap hypothesis could be formed.")]
        return [self._build_result(business, research, vertical, otype, support)
                for otype, support in ranked[:max_hypotheses]]

    # -- signal collection --------------------------------------------------
    def _collect_signals(
        self,
        research: BusinessResearch,
        vertical: VerticalType,
    ) -> dict:
        """Aggregate verified observations into typed signal buckets."""
        facts = [e for e in research.evidence if e.claim_type == ClaimType.VERIFIED_FACT]
        facts_by_cat = {c: [e for e in facts if e.category == c] for c in EvidenceCategory}

        signals: dict = {
            "has_booking": research.booking_system_found or bool(facts_by_cat[EvidenceCategory.BOOKING_FLOW]),
            "has_ordering": research.ordering_system_found or bool(facts_by_cat[EvidenceCategory.ORDERING_FLOW]),
            "has_website": research.website_exists,
            "mobile_friendly": research.is_mobile_friendly,
            "speed_score": research.speed_score,
            "phone_only_contact": (
                facts_by_cat[EvidenceCategory.CONTACT_FLOW]
                or (research.contact_methods and any("phone" in c.lower() for c in research.contact_methods))
            ),
            "whatsapp_present": any("whatsapp" in c.lower() for c in research.contact_methods or []),
            "weaknesses": list(research.observed_weaknesses or []),
            "strengths": list(research.observed_strengths or []),
            "tech_signals": list(research.tech_stack or []),
            "appointment_vertical": vertical in VERTICAL_BOOKING_APPT,
            "consultative_vertical": vertical in VERTICAL_CONSULTATIVE,
            "ordering_vertical": vertical in VERTICAL_ORDERING,
            "evidence": facts,
        }
        return signals

    # -- hypothesis ranking -------------------------------------------------
    def _rank_hypotheses(
        self,
        s: dict,
        vertical: VerticalType,
    ) -> List[Tuple[OpportunityType, List[ResearchEvidence]]]:
        """Return opportunity hypotheses sorted by evidence support strength."""
        e = s["evidence"]
        hyp: List[Tuple[OpportunityType, List[ResearchEvidence]]] = []

        # ONLINE_BOOKING: appointment-style vertical missing self-serve booking.
        booking_ev = [x for x in e if x.category in (EvidenceCategory.BOOKING_FLOW, EvidenceCategory.CONTACT_FLOW)]
        if s["appointment_vertical"] and not s["has_booking"]:
            support = booking_ev or [x for x in e if x.category == EvidenceCategory.IDENTITY]
            hyp.append((OpportunityType.ONLINE_BOOKING, support[:4]))

        # LEAD_CAPTURE: consultative/service vertical without obvious self-serve inquiry capture.
        captive_ev = [x for x in e if x.category in (EvidenceCategory.CONTACT_FLOW, EvidenceCategory.SERVICES)]
        if s["consultative_vertical"] and not s["has_booking"]:
            support = captive_ev or [x for x in e if x.category == EvidenceCategory.IDENTITY]
            hyp.append((OpportunityType.LEAD_CAPTURE, support[:4]))

        # ORDERING_SYSTEM: food/retail vertical without online ordering.
        ordering_ev = [x for x in e if x.category == EvidenceCategory.ORDERING_FLOW]
        if s["ordering_vertical"] and not s["has_ordering"]:
            support = ordering_ev or [x for x in e if x.category == EvidenceCategory.IDENTITY]
            hyp.append((OpportunityType.ORDERING_SYSTEM, support[:4]))

        # WEBSITE_MODERNIZATION: no website, or site with mobile/quality problems.
        web_ev = [x for x in e if x.category in (EvidenceCategory.MOBILE_UX, EvidenceCategory.TECH_STACK)]
        no_website = s["has_website"] is False
        weak_website = s["has_website"] is True and (
            s["mobile_friendly"] is False or (s["speed_score"] is not None and s["speed_score"] < 50)
        )
        if no_website or weak_website:
            support = web_ev or (e[:2] if no_website else [])
            hyp.append((OpportunityType.WEBSITE_MODERNIZATION, support[:4]))

        # CUSTOMER_PORTAL: booking exists but no account/self-service layer.
        if s["has_booking"] and s["appointment_vertical"]:
            portal_ev = booking_ev or e[:2]
            hyp.append((OpportunityType.CUSTOMER_PORTAL, portal_ev[:3]))

        # WHATSAPP_AUTOMATION: phone/whatsapp-based enquiries in a service vertical.
        if s["whatsapp_present"] or s["phone_only_contact"]:
            wa_ev = [x for x in e if x.category in (EvidenceCategory.CONTACT_FLOW, EvidenceCategory.BOOKING_FLOW)]
            hyp.append((OpportunityType.WHATSAPP_AUTOMATION, wa_ev[:3]))

        # CUSTOM_WEBAPP: explicit observed operational friction in weaknesses.
        friction_ev = [x for x in e if x.category == EvidenceCategory.SERVICES]
        if s["weaknesses"]:
            hyp.append((OpportunityType.CUSTOM_WEBAPP, (friction_ev[:2] if friction_ev else []) or e[:2]))

        # De-duplicate confirmed by type, then score by support quality.
        seen: set = set()
        unique: List[Tuple[OpportunityType, List[ResearchEvidence]]] = []
        for otype, support in hyp:
            if otype in seen:
                continue
            seen.add(otype)
            unique.append((otype, support))

        def _support_key(item: Tuple[OpportunityType, List[ResearchEvidence]]) -> Tuple[float, int]:
            otype, support = item
            n = len(support)
            avg_conf = sum(x.confidence for x in support) / n if n else 0.0
            any_fact = any(x.claim_type == ClaimType.VERIFIED_FACT for x in support)
            # Verified-fact/confidence weigh more than the raw count.
            return (1.0 if any_fact else 0.0, round(avg_conf, 3))
            # (kept simple: any_fact + avg confidence dominates)

        unique.sort(key=_support_key, reverse=True)
        return unique

    # -- result builder -----------------------------------------------------
    def _build_result(
        self,
        business: BusinessRecord,
        research: BusinessResearch,
        vertical: VerticalType,
        otype: OpportunityType,
        support: List[ResearchEvidence],
    ) -> AnalysisResult:
        """Construct a fully traceable AnalysisResult for the chosen hypothesis."""
        commodity = self._build_narrative(business, research, vertical, otype, support)
        if not support:
            return self._insufficient(
                business,
                f"Hypothesis {otype.value} formed but no supporting evidence found; refusing to manufacture.",
            )

        evidence_ids = [e.id for e in support]
        claims = [e.claim for e in support]
        reasoning = [f"Supported by claim [{e.id}]: {e.claim}" for e in support]
        conf = self._confidence(research, support)
        risks, unknowns = self._risks_and_unknowns(research, otype)

        return AnalysisResult(
            business_id=business.id,
            opportunity_type=otype,
            title=commodity["title"],
            problem_summary=commodity["problem"],
            proposed_solution=commodity["solution"],
            business_value=commodity["value"],
            rationale=commodity["rationale"],
            confidence=conf,
            implementation_effort=commodity["effort"],
            risks=risks,
            unknowns=unknowns,
            evidence_ids=evidence_ids,
            supporting_claims=claims,
            reasoning=reasoning,
            sufficient_evidence=True,
        )

    # -- narrative builders ------------------------------------------------
    def _build_narrative(self, business: BusinessRecord, research: BusinessResearch, vertical: VerticalType, otype: OpportunityType, support: List[ResearchEvidence]) -> dict:
        """Compose honest, specific narrative text for each opportunity type."""
        services = research.services or []
        svc = ", ".join(services[:3]) if services else "your services"

        if otype == OpportunityType.ONLINE_BOOKING:
            weakness_desc = research.observed_weaknesses[0] if research.observed_weaknesses else f"no self-serve online booking system found for {business.name}"
            return {
                "title": f"24/7 Digital Booking Engine for {business.name}",
                "problem": f"Operational friction observed at {business.name} ({business.city}): {weakness_desc}.",
                "solution": f"A mobile-first appointment booking platform tailored for {business.name} with automated instant confirmation & reminders.",
                "value": "Reduces phone-tag, cuts missed appointments, and captures bookings outside working hours.",
                "rationale": f"The business ({business.name}) shows appointment demand in {business.city} but lacks an automated self-serve booking portal.",
                "effort": "low" if not research.is_mobile_friendly else "medium",
            }
        if otype == OpportunityType.LEAD_CAPTURE:
            weakness_desc = research.observed_weaknesses[0] if research.observed_weaknesses else f"no structured inquiry intake flow found for {business.name}"
            return {
                "title": f"Lead Capture & Digital Intake System for {business.name}",
                "problem": f"Inbound inquiry friction at {business.name} ({business.city}): {weakness_desc}.",
                "solution": f"A high-converting digital storefront and instant qualification form tailored for {business.name}.",
                "value": "Captures enquiries that are currently lost between phone/chat/email, and makes follow-up consistent.",
                "rationale": f"The business ({business.name}) is consultative/service-led in {business.city}; capturing inbound intent cleanly is high-leverage.",
                "effort": "low",
            }
        if otype == OpportunityType.ORDERING_SYSTEM:
            weakness_desc = research.observed_weaknesses[0] if research.observed_weaknesses else f"no digital ordering catalog found for {business.name}"
            return {
                "title": f"Direct Digital Menu & Order Platform for {business.name}",
                "problem": f"Manual order processing observed at {business.name} ({business.city}): {weakness_desc}.",
                "solution": f"An interactive menu & direct ordering web app for {business.name} with instant WhatsApp/SMS notification.",
                "value": "Wins orders beyond business hours and reduces ordering friction on high-traffic channels.",
                "rationale": f"The business ({business.name}) sits in {vertical.value} where digital ordering drives direct high-margin revenue.",
                "effort": "low" if not research.ordering_system_found else "medium",
            }
        if otype == OpportunityType.WEBSITE_MODERNIZATION:
            weakness_desc = research.observed_weaknesses[0] if research.observed_weaknesses else f"lacks a 24/7 automated self-serve web booking engine"
            return {
                "title": f"Bespoke Commercial Web Presence & Digital Booking Engine for {business.name}",
                "problem": f"Digital experience friction at {business.name} ({business.city}): {weakness_desc}.",
                "solution": f"A 3-page modern commercial website prototype featuring showcase hero, interactive rate card, and 24/7 digital booking engine for {business.name}.",
                "value": "Provides a high-converting digital storefront & automated self-serve booking portal for customers in {business.city}.",
                "rationale": f"Digital experience friction observed for {business.name}; implementing a modern 3-page web platform elevates conversion.",
                "effort": "low",
            }
            return {
                "title": f"Website Modernization & Digital Experience for {business.name}",
                "problem": f"Digital experience friction at {business.name} ({business.city}): {weakness_desc}.",
                "solution": f"A redesigned, fast, mobile-first commercial web experience tailored for {business.name}.",
                "value": "Improves conversion from mobile visitors, who dominate local search traffic in India.",
                "rationale": f"The site for {business.name} was observed during research with usability or quality friction.",
                "effort": "medium",
            }
        if otype == OpportunityType.CUSTOMER_PORTAL:
            return {
                "title": "Customer Self-Service Portal",
                "problem": "Bookings exist, but no customer self-service layer (status, reschedule, reminders) was observed.",
                "solution": "A customer portal for booking status, rescheduling, and automated reminders on top of the existing booking flow.",
                "value": "Cuts no-shows and phone-based reschedules while improving the customer experience.",
                "rationale": "Appointment-style business with an existing booking system but no observable self-service layer.",
                "effort": "medium",
            }
        if otype == OpportunityType.WHATSAPP_AUTOMATION:
            return {
                "title": "WhatsApp Enquiry Automation",
                "problem": "Enquiries currently arrive over phone/WhatsApp with no structured capture or auto-response.",
                "solution": "An automated WhatsApp inflow: instant acknowledgement, structured capture, and handoff to a human.",
                "value": "Responds instantly on the channel customers already use, and organises enquiries in one inbox.",
                "rationale": "Phone/WhatsApp contact flow was observed, which is where this automation pays off fastest.",
                "effort": "medium",
            }
        # CUSTOM_WEBAPP default
        weaknesses = ", ".join(research.observed_weaknesses[:2]) if research.observed_weaknesses else "manual workflows"
        return {
            "title": "Custom Workflow Application",
            "problem": f"Operational friction was observed in research: {weaknesses}.",
            "solution": "A custom web application automating the specific observed workflow, built to fit the business's exact process.",
            "value": "Removes the repetitive manual handling that consumes staff time day-to-day.",
            "rationale": "Verified observations of operational friction were recorded during research.",
            "effort": "high",
        }

    def _confidence(self, research: BusinessResearch, support: List[ResearchEvidence]) -> float:
        """Confidence that the identified opportunity reflects a genuine gap.

        Confidence is intentionally SEPARATE from the opportunity score: it
        measures how well-evidenced the hypothesis is, not how valuable it is.
        """
        if not support:
            return 0.0
        relevant = [e for e in research.evidence
                    if e.category in (EvidenceCategory.BOOKING_FLOW, EvidenceCategory.CONTACT_FLOW,
                                      EvidenceCategory.ORDERING_FLOW, EvidenceCategory.MOBILE_UX,
                                      EvidenceCategory.TECH_STACK, EvidenceCategory.SERVICES)]
        n = len(research.evidence) or 1
        verified = sum(1 for e in research.evidence if e.claim_type == ClaimType.VERIFIED_FACT)
        support_conf = sum(e.confidence for e in support) / len(support)
        confidence = 0.35 * (verified / n) + 0.45 * support_conf
        if research.observed_weaknesses or research.observed_strengths:
            confidence += 0.15
        if research.website_exists is False:
            confidence -= 0.1
        return round(max(0.0, min(1.0, confidence)), 3)

    def _risks_and_unknowns(self, research: BusinessResearch, otype: OpportunityType) -> Tuple[List[str], List[str]]:
        """Surface genuine uncertainties rather than hidden assumptions."""
        risks: List[str] = []
        unknowns: List[str] = []
        if research.website_exists is False:
            risks.append("No website exists; the business may already run fully offline by choice.")
        elif research.website_exists and research.speed_score is None:
            unknowns.append("Site speed was not measured; competitiveness of the current page is unverified.")
        if research.pricing_info is None:
            unknowns.append("Pricing model unknown; value framing may need adjustment for this business.")
        if not research.social_links:
            unknowns.append("Social footprint not observed; channel preferences unverified.")
        if research.is_mobile_friendly is None:
            unknowns.append("Mobile experience unverified — assume of-the-time status until confirmed.")
        if len(risks) == 0 and len(unknowns) == 0:
            unknowns.append("Customer intent is inferred from public signals, not confirmed — soft-open outreach recommended.")
        return risks[:4], unknowns[:4]

    def _reasoning_lines(self, research, otype, support, commodity) -> List[str]:
        lines = [f"Detected gap: {commodity['problem'][:140]}"]
        for ev in support[:3]:
            kind = "verified fact" if ev.claim_type == ClaimType.VERIFIED_FACT else ev.claim_type.value
            lines.append(f"Supporting {kind}: {ev.claim[:160]}")
        lines.append(f"Proposed solution: {commodity['solution'][:160]}")
        return lines

    @staticmethod
    def _insufficient(business: BusinessRecord, reason: str) -> AnalysisResult:
        return AnalysisResult(
            business_id=business.id,
            rationale=reason,
            insufficient_reason=reason,
            sufficient_evidence=False,
        )