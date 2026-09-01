"""Inbound response AI classifier + suggested-reply generator.

Deterministic, keyword-anchored classifier that maps free-form reply text onto
the ResponseClassification enum. Human override is always possible (the reply
is stored in PENDING_REVIEW and the dashboard lets the operator re-classify).

Also detects opt-out / wrong-contact signals so the follow-up engine can
suppress future outreach even before the enum gain adds dedicated members.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field as dc_field
from typing import List, Optional

from b2b.models import (
    BusinessRecord,
    OpportunityRecord,
    OutreachRecord,
    ResponseClassification,
)

logger = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    classification: ResponseClassification
    confidence: float
    matched_signals: List[str] = dc_field(default_factory=list)
    suppression_signal: bool = False      # opt-out / wrong-contact / hard-negative
    disputed: bool = False                # conflicting signals -> show for human review

    def api_dict(self) -> dict:
        return {
            "classification": self.classification.value,
            "confidence": round(self.confidence, 3),
            "matched_signals": self.matched_signals,
            "suppression_signal": self.suppression_signal,
            "disputed": self.disputed,
        }


# Keyword rules: (label, regex patterns, weight, classification, suppression)
_RULES: List[tuple] = [
    ("unsubscribe", [r"\bunsub\w*\b", r"opt\s*out", r"stop email", r"take\s*me\s*off",
                     r"remove.*(?:list|mail)", r"no more emails", r"do not (?:contact|email)",
                     r"please\s+stop"], -2.0,
     ResponseClassification.UNSUBSCRIBED, True),
    ("wrong_contact", [r"wrong (?:person|number|contact|recipient)", r"don'?t know this",
                       r"not the (?:right|correct) person", r"no one (?:here|by that)", r"mistake"],
     2.0, ResponseClassification.WRONG_CONTACT, True),
    ("bounced", [r"delivery.*fail", r"mailbox.*(?:full|doesn'?t exist)", r"address.*(?:undeliverable|not found)",
                 r"no such (?:user|recipient|account)", r"550", r"user unknown"], 2.0,
     ResponseClassification.BOUNCED, True),
    ("meeting", [r"(?:schedule|book|set\s*up|fix)\b.*(?:meet|call|demo)", r"meeting (?:request|time|slot)",
                 r"how about (?:tomorrow|today|monday|this week)", r"(?:call|talk|speak).*(?:tomorrow|today|monday)",
                 r"available (?:for|to).*(?:call|meet)", r"wants? a (?:meeting|call)"], 3.0,
     ResponseClassification.WANTS_MEETING, False),
    ("interested", [r"sounds (?:interesting|great|good|good)", r"interested", r"would love to",
                    r"please (?:share|send|show)", r"i\s*'?d like to (?:see|know|learn|talk)",
                    r"(?:how does|let'?s) (?:this|it) work", r"tell me more", r"yes(?:,|!| )"], 1.5,
     ResponseClassification.INTERESTED, False),
    ("question", [r"\?", r"how (?:much|long|does)", r"what(?:'| i)?s the (?:cost|price|pricing)",
                  r"is this (?:free|paid)", r"explain"], 1.0,
     ResponseClassification.QUESTION, False),
    ("pricing", [r"(?:cost|price|pricing|charge|fee|budget)", r"how much"], 3.0,
     ResponseClassification.WANTS_PRICING, False),
    ("office", [r"out\s*of\s*office", r"on (?:leave|vacation|holiday)", r"will respond", r"back on"], 3.0,
     ResponseClassification.OUT_OF_OFFICE, False),
    ("negative", [r"not interested", r"no (?:thanks|thank you|thx)", r"don'?t (?:need|want)",
                  r"already (?:have|use) (?:something|a tool)", r"not (?:for|the right) fit",
                  r"waste of (?:time|money)", r"stop contacting"], -2.0,
     ResponseClassification.NOT_INTERESTED, False),
]


class ResponseClassifier:
    """Classifies inbound outreach responses with explainable signals."""

    def __init__(self) -> None:
        self._compiled = [
            (label, [re.compile(p, re.IGNORECASE) for p in pats], weight, cls, supp)
            for label, pats, weight, cls, supp in _RULES
        ]

    def classify(self, raw: str) -> ClassificationResult:
        text = (raw or "").strip()
        if not text:
            return ClassificationResult(ResponseClassification.UNCLEAR, 0.0,
                                        matched_signals=["empty content"])

        scores: dict[str, float] = {}
        matched: List[str] = []
        suppression = False
        for label, pats, weight, cls, supp in self._compiled:
            hit = any(p.search(text) for p in pats)
            if hit:
                scores[label] = scores.get(label, 0.0) + weight
                matched.append(label)
                if supp:
                    suppression = True

        if not scores:
            return ClassificationResult(ResponseClassification.UNCLEAR, 0.3,
                                        matched_signals=["no signal keywords matched"])

        best_label = max(scores, key=scores.get)
        cls_map = {
            "meeting": ResponseClassification.WANTS_MEETING,
            "pricing": ResponseClassification.WANTS_PRICING,
            "office": ResponseClassification.OUT_OF_OFFICE,
            "bounced": ResponseClassification.BOUNCED,
            "interested": ResponseClassification.INTERESTED,
            "question": ResponseClassification.QUESTION,
            "negative": ResponseClassification.NOT_INTERESTED,
            "unsubscribe": ResponseClassification.UNSUBSCRIBED,
            "wrong_contact": ResponseClassification.WRONG_CONTACT,
        }
        classification = cls_map[best_label]

        # Confidence based on strength vs. runner-up, plus how many signals agreed.
        n = len(scores)
        total = sum(scores.values())
        confidence = min(0.95, 0.35 + 0.1 * n + 0.1 * max(0.0, scores[best_label] - max(
            (v for k, v in scores.items() if k != best_label), default=0.0)))

        if classification == ResponseClassification.WANTS_MEETING and "pricing" in scores:
            classification = ResponseClassification.WANTS_MEETING  # meeting outranks pricing intent
        disputed = bool(
            ("interested" in scores and "negative" in scores)
            or ("interested" in scores and "unsubscribe" in scores)
        )
        # Bounce detection overrides interest (delivery failures are not replies).
        if best_label in ("bounced", "wrong_contact"):
            classification = cls_map[best_label]
            confidence = min(0.95, confidence + 0.05)

        return ClassificationResult(
            classification=classification,
            confidence=round(max(0.1, min(0.97, confidence)), 3),
            matched_signals=matched,
            suppression_signal=suppression,
            disputed=disputed,
        )

    def classify_records(
        self,
        outreach: OutreachRecord,
        raw: str,
        business: Optional[BusinessRecord] = None,
        opp: Optional[OpportunityRecord] = None,
        suggest: bool = True,
    ) -> "ClassifiedResponse":
        """Full one-shot: classify + attach a suggested reply."""
        result = self.classify(raw)
        reply: Optional[str] = None
        if suggest:
            reply = self.suggest_reply(raw, result.classification, outreach)
        return ClassifiedResponse(
            outreach_id=outreach.id,
            business_id=outreach.business_id,
            raw_content=raw,
            classification=result.classification,
            confidence=result.confidence,
            matched_signals=result.matched_signals,
            suppression_signal=result.suppression_signal,
            disputed=result.disputed,
            suggested_reply=reply,
        )

    # -- suggested replies -------------------------------------------------
    def suggest_reply(self, raw: str, cls: ResponseClassification,
                      outreach: OutreachRecord) -> Optional[str]:
        """A first-pass reply candidate; always human-reviewed before send."""
        if cls == ResponseClassification.WANTS_MEETING:
            return (
                "Happy to. Could you confirm two times that suit you this week "
                "and I will send a calendar invite?"
            )
        if cls == ResponseClassification.INTERESTED:
            return (
                "Great to hear. Would you like me to walk you through the demo "
                "at a time that suits you - or shall I send more details first?"
            )
        if cls == ResponseClassification.QUESTION:
            return (
                "Good question - and happy to answer in more detail on a short "
                "call. In the meantime, what aspect would you like me to focus on first?"
            )
        if cls == ResponseClassification.WANTS_PRICING:
            return (
                "Happy to share. Depending on exactly what we scope, engagements "
                "for this style of build typically land in a clear, predictable band - "
                "may I ask 2 quick questions about your current setup so the number is honest?"
            )
        if cls == ResponseClassification.NOT_INTERESTED:
            return (
                "Thanks for letting me know - completely understood. I will not "
                "follow up on this again. Appreciate your time."
            )
        if cls == ResponseClassification.OUT_OF_OFFICE:
            return None
        if cls == ResponseClassification.BOUNCED:
            return None
        if cls == ResponseClassification.UNSUBSCRIBED:
            return "Understood - you've been unsubscribed and will not hear from us again."
        if cls == ResponseClassification.WRONG_CONTACT:
            return "My apologies for the interruption. You can safely ignore this - I'll make sure this contact is not emailed again."
        return "Thanks for the note - could you confirm what you had in mind so I can point you to the right person?"


@dataclass
class ClassifiedResponse:
    outreach_id: str
    business_id: str
    raw_content: str
    classification: ResponseClassification
    confidence: float
    matched_signals: List[str] = dc_field(default_factory=list)
    suppression_signal: bool = False
    disputed: bool = False
    suggested_reply: Optional[str] = None

    def api_dict(self) -> dict:
        return {
            "outreach_id": self.outreach_id,
            "business_id": self.business_id,
            "classification": self.classification.value,
            "confidence": self.confidence,
            "matched_signals": self.matched_signals,
            "suppression_signal": self.suppression_signal,
            "disputed": self.disputed,
            "suggested_reply": self.suggested_reply,
        }