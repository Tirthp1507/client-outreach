"""Personalized outreach copy generator.

Produces traceable, non-spam email drafts built from the research evidence of
a specific business. Every personalization claim is backed by a
personalization_reason and the source evidence ids/claims that ground it.

Structure per the product spec:
Subject -> Personal observation -> Identified problem -> Relevant solution ->
Specific reason it may matter -> Demo link -> Low-friction CTA -> Closing.

No business fact is invented; uncertain framing is used when the evidence is
thin, and recipients are never addressed by a fabricated name.
"""

from __future__ import annotations

import html as _html
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from b2b.models import (
    ApprovalStatus,
    BusinessRecord,
    BusinessResearch,
    DemoRecord,
    OpportunityRecord,
    OpportunityType,
    OutreachRecord,
    ResearchEvidence,
    SendStatus,
)

logger = logging.getLogger(__name__)


class OutreachDraft:
    """A generated outreach variant (plain text + reasons), pre-persistence."""

    def __init__(self, subject: str, body_text: str, followup_body: str,
                 personalization_reasons: List[str], evidence_used: List[str],
                 body_html: str = "") -> None:
        self.subject = subject
        self.body_text = body_text
        self.followup_body = followup_body
        self.personalization_reasons = personalization_reasons
        self.evidence_used = evidence_used
        self.body_html = body_html


def _days_phrase() -> str:
    return "a few days"


class OutreachGenerator:
    """Builds personalized outreach variants from verified research."""

    def __init__(self, variants: int = 2) -> None:
        self.variants = variants

    # -- public ------------------------------------------------------------
    def generate(
        self,
        business: BusinessRecord,
        opp: OpportunityRecord,
        demo: Optional[DemoRecord],
        research: Optional[BusinessResearch],
    ) -> List[OutreachDraft]:
        """Create 1-3 outreach variants, main one first."""
        evidence = self._relevant_evidence(research, opp)
        drafts = [self._variant_specific_gap(business, opp, demo, evidence)]
        if self.variants >= 2:
            drafts.append(self._variant_value_first(business, opp, demo, evidence))
        if self.variants >= 3:
            drafts.append(self._variant_short(business, opp, demo, evidence))
        return drafts

    def to_records(
        self,
        business: BusinessRecord,
        opp: OpportunityRecord,
        demo: Optional[DemoRecord],
        drafts: List[OutreachDraft],
    ) -> List[OutreachRecord]:
        """Convert drafts into persistable OutreachRecords (PENDING_REVIEW)."""
        records: List[OutreachRecord] = []
        now = datetime.now(timezone.utc).isoformat()
        for i, d in enumerate(drafts, start=1):
            suffix = "" if i == 1 else f" (variant {i})"
            records.append(OutreachRecord(
                id=f"out_{uuid.uuid4().hex[:10]}",
                business_id=business.id,
                opportunity_id=opp.id,
                demo_id=demo.id if demo else None,
                recipient_email=business.email or "",
                recipient_name=None,
                subject=d.subject + suffix,
                body_text=d.body_text,
                body_html=d.body_html or self._html_body(d.body_text),
                followup_body=d.followup_body,
                personalization_reasons=d.personalization_reasons,
                evidence_used=d.evidence_used,
                approval_status=ApprovalStatus.PENDING_REVIEW,
                send_status=SendStatus.DRAFT,
                created_at=now,
            ))
        return records

    # -- evidence selection ------------------------------------------------
    @staticmethod
    def _relevant_evidence(research: Optional[BusinessResearch],
                           opp: OpportunityRecord) -> List[ResearchEvidence]:
        if not research:
            return []
        by_id = {e.id: e for e in research.evidence}
        picked = [by_id[i] for i in opp.evidence_ids if i in by_id]
        if picked:
            return picked[:4]
        # Fall back to factual evidence about the gap categories.
        cats = ("booking", "order", "contact", "tech", "mobile")
        return [e for e in research.evidence
                if e.claim_type.value == "verified_fact"
                and any(c in e.category.value for c in cats)][:4]

    # -- variant builders --------------------------------------------------
    def _variant_specific_gap(self, business, opp, demo, evidence) -> OutreachDraft:
        observation = self._observation(evidence, business)
        subject = self._subject(business, opp)
        demo_link = f"{demo.preview_url}" if demo else "the working prototype"

        body_lines = [
            f"Hello team at {business.name},",
            "",
            observation["opener"],
            "",
            f"Specifically: {opp.problem_summary}",
            "",
            f"The kind of thing I have in mind is {opp.proposed_solution}. "
            f"You can click through a working prototype here: {demo_link}",
            "",
            f"Why this may matter: {opp.business_value}",
            "",
            "Would a 15-minute walkthrough of this prototype make sense? If it is "
            "the wrong priority for you right now, no problem at all - just say so.",
            "",
            "Best regards,",
            "Your contact here at our studio",
        ]
        reasons = self._reasons(evidence, opp, "observation-first variant")
        return OutreachDraft(
            subject=subject,
            body_text="\n".join(body_lines),
            followup_body=self._followup(business, opp, demo),
            personalization_reasons=reasons,
            evidence_used=[e.claim for e in evidence],
        )

    def _variant_value_first(self, business, opp, demo, evidence) -> OutreachDraft:
        demo_link = f"{demo.preview_url}" if demo else "the working prototype"
        body_lines = [
            f"Hello team at {business.name},",
            "",
            f"A short idea for {business.name.rstrip('.')} in {business.city}: "
            f"{opp.business_value}",
            "",
            f"The automation I would propose: {opp.proposed_solution}. "
            f"It addresses the point that {opp.problem_summary}",
            "",
            f"You can try the interactive prototype here: {demo_link}",
            "",
            "Happy to walk you through it live - it takes about 10 minutes. "
            "If this is not what you need right now, feel free to ignore this; "
            "no follow-ups if it is not interesting to you.",
            "",
            "Warm regards,",
            "Your contact here at our studio",
        ]
        return OutreachDraft(
            subject=self._subject(business, opp),
            body_text="\n".join(body_lines),
            followup_body=self._followup(business, opp, demo),
            personalization_reasons=self._reasons(evidence, opp, "value-first variant"),
            evidence_used=[e.claim for e in evidence],
        )

    def _variant_short(self, business, opp, demo, evidence) -> OutreachDraft:
        demo_link = f"{demo.preview_url}" if demo else "the working prototype"
        body_text = (
            f"Hello {business.name} team,\n\n"
            f"Running idea: {opp.proposed_solution} - because {opp.problem_summary}\n\n"
            f"Working prototype: {demo_link}\n\n"
            "Open to a short call to see if it fits? If not, no worries.\n\n"
            "Thanks."
        )
        return OutreachDraft(
            subject=f"Quick idea for {business.name}: {opp.opportunity_type.value.replace('_', ' ')}",
            body_text=body_text,
            followup_body=self._followup(business, opp, demo),
            personalization_reasons=self._reasons(evidence, opp, "short variant"),
            evidence_used=[e.claim for e in evidence],
        )

    # -- reusable fragments ------------------------------------------------
    def _observation(self, evidence: List[ResearchEvidence], business) -> dict:
        """A specific, evidence-based observation; soft framing when thin."""
        if evidence:
            strongest = evidence[0]
            opener = (
                f"I was researching {business.category} businesses in {business.city} and "
                f"noticed something about {business.name}: {strongest.claim}"
            )
            return {"opener": opener, "claim": strongest.claim}
        opener = (
            f"I was researching {business.category} businesses in {business.city} and "
            "wanted to share one low-effort idea that often helps businesses like yours. "
            "I might be wrong about the fit, so take it as simply an offer."
        )
        return {"opener": opener, "claim": ""}

    @staticmethod
    def _subject(business: BusinessRecord, opp: OpportunityRecord) -> str:
        what = opp.opportunity_type.value.replace("_", " ")
        return f"Quick idea for {business.name}: a {what} within {_days_phrase()}"

    @staticmethod
    def _reasons(evidence: List[ResearchEvidence], opp: OpportunityRecord, variant: str) -> List[str]:
        reasons = [f"{variant} grounded in verified research evidence"]
        reasons.extend(f"Evidence {e.id}: {e.claim}" for e in evidence[:3])
        if not evidence:
            reasons.append("No verified claims available - message uses soft, non-factual framing only")
        return reasons

    @staticmethod
    def _followup(business, opp, demo) -> str:
        demo_link = f"{demo.preview_url}" if demo else "the working prototype"
        return (
            f"Hello again {business.name} team,\n\n"
            "Just in case my earlier note landed in a busy inbox - the offer stands: "
            f"{opp.proposed_solution}, demonstrated live in {demo_link}. "
            f"If this is not relevant for {business.name} right now, it is completely "
            "fine - just reply 'no thanks' and I will not write again about it.\n\n"
            "Best regards,"
        )

    @staticmethod
    def _html_body(text: str) -> str:
        safe = _html.escape(text)
        paragraphs = [f"<p>{p}</p>" for p in safe.split("\n") if p.strip()]
        return "\n".join(paragraphs)