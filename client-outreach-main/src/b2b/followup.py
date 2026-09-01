"""Follow-up intelligence: Day-0 / Day-3 / Day-7 cadence scheduling.

Computes from the persisted outreach + response records which sent
conversations are due for a follow-up, and stages them as ``FollowUpRecord``
rows in the shared ``followups`` table (Jim's Phase J persistence). Every
follow-up is stored PENDING_REVIEW and must pass the same human approval gate
as first-contact email before anything can be dispatched.

Follow-ups are SUPPRESSED (never scheduled) for any thread that:

* has a response classified UNSUBSCRIBED / WRONG_CONTACT / NOT_INTERESTED /
  BOUNCED, or which reads like an opt-out, or
* comes from a recipient on the explicit suppression list, or
* already reached the configured maximum number of follow-ups.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Set, Tuple

from b2b.models import (
    FollowUpRecord,
    FollowUpStatus,
    OutreachRecord,
    ResponseClassification,
    SendStatus,
)
from b2b.response_classifier import ResponseClassifier

# NOTE: `db.database.Database` is imported lazily inside methods to avoid the
# db.database <-> b2b.models <-> b2b package init import cycle.

logger = logging.getLogger(__name__)

TERMINAL_CLASSES = {
    ResponseClassification.UNSUBSCRIBED,
    ResponseClassification.WRONG_CONTACT,
    ResponseClassification.NOT_INTERESTED,
    ResponseClassification.BOUNCED,
}


@dataclass
class FollowUpPolicy:
    cadence_days: List[int] = dc_field(default_factory=lambda: [3, 7])
    max_followups: int = 2
    enabled: bool = True
    suppression_emails: Set[str] = dc_field(default_factory=set)

    @property
    def days_by_step(self) -> dict:
        return {i + 1: d for i, d in enumerate(self.cadence_days[: self.max_followups])}


@dataclass
class FollowUpPlan:
    """A computed follow-up action (read-only diagnostic)."""
    outreach_id: str
    business_id: str
    step: int
    scheduled_date: str
    subject: str
    body_text: str
    eligible: bool
    reason: str


class FollowUpIntelligence:
    """Determines due follow-ups and persists them as FollowUpRecord drafts."""

    def __init__(self, classifier: Optional[ResponseClassifier] = None) -> None:
        self.classifier = classifier or ResponseClassifier()

    # -- diagnostics (read-only) ------------------------------------------
    def plan(self, db: Database, policy: Optional[FollowUpPolicy] = None,
             today: Optional[datetime] = None) -> List[FollowUpPlan]:
        policy = policy or FollowUpPolicy()
        today = today or datetime.now(timezone.utc)
        plans: List[FollowUpPlan] = []
        for out in self._sent_outreaches(db):
            plans.append(self._plan_for(out, db, policy, today))
        return plans

    def _plan_for(self, out: OutreachRecord, db: Database, policy: FollowUpPolicy,
                  today: datetime) -> FollowUpPlan:
        result = self._check(out, db, policy, today)
        reason, blocked, terms = result
        step, scheduled = terms if terms else (0, "")
        return FollowUpPlan(
            outreach_id=out.id,
            business_id=out.business_id,
            step=step,
            scheduled_date=scheduled,
            subject=self._subject(out, step) if not blocked else "",
            body_text=out.followup_body or self._default_body(out) if not blocked else "",
            eligible=not blocked,
            reason=reason,
        )

    # -- staging (persist pending-review follow-ups) -----------------------
    def plan_and_stage(
        self,
        db: Database,
        policy: Optional[FollowUpPolicy] = None,
        today: Optional[datetime] = None,
    ) -> Tuple[List[FollowUpRecord], List[FollowUpPlan]]:
        """Persist eligible follow-ups as PENDING_REVIEW FollowUpRecord rows.

        Returns (staged records, all computed plans). No sends happen here.
        """
        policy = policy or FollowUpPolicy()
        today = today or datetime.now(timezone.utc)
        staged: List[FollowUpRecord] = []
        for plan in self.plan(db, policy, today):
            if not plan.eligible:
                continue
            if self._already_staged(db, plan):
                continue
            staged.append(self._stage_record(db, plan))
        return staged, self.plan(db, policy, today)

    def _already_staged(self, db: Database, plan: FollowUpPlan) -> bool:
        existing = db.list_followups(outreach_id=plan.outreach_id, limit=100)
        return any(f.step_number == plan.step and f.status in (
            FollowUpStatus.PENDING_REVIEW, FollowUpStatus.APPROVED, FollowUpStatus.SENT
        ) for f in existing)

    def _stage_record(self, db: Database, plan: FollowUpPlan) -> FollowUpRecord:
        record = FollowUpRecord(
            id=f"fup_{uuid.uuid4().hex[:10]}",
            outreach_id=plan.outreach_id,
            business_id=plan.business_id,
            step_number=plan.step,
            scheduled_date=plan.scheduled_date,
            subject=plan.subject,
            body_text=plan.body_text,
            status=FollowUpStatus.PENDING_REVIEW,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return db.save_followup(record)

    # -- gating logic ------------------------------------------------------
    def _check(
        self,
        out: OutreachRecord,
        db: Database,
        policy: FollowUpPolicy,
        today: datetime,
    ) -> Tuple[str, bool, Optional[Tuple[int, str]]]:
        if not policy.enabled:
            return "follow-up policy disabled", True, None

        sent_at = self._parse_sent_at(out.sent_at)
        if sent_at is None:
            return "outreach has no send timestamp - cannot schedule follow-up", True, None

        if (out.recipient_email or "").lower() in {e.lower() for e in policy.suppression_emails}:
            return "recipient is on the suppression list", True, None

        latest = self._latest_response(db, out.id)
        if latest is not None:
            if latest.classification in TERMINAL_CLASSES:
                return f"thread has a terminal response ({latest.classification.value}) - suppressed", True, None
            if self.classifier.classify(latest.raw_content).suppression_signal:
                return "thread response looks like an opt-out - suppressed", True, None

        active = [f for f in db.list_followups(outreach_id=out.id, limit=100)
                  if f.status not in (FollowUpStatus.SUPPRESSED, FollowUpStatus.CANCELLED)]
        if len(active) >= policy.max_followups:
            return f"already issued {len(active)} follow-up(s); max reached", True, None

        days = (today - sent_at).days
        days_by_step = policy.days_by_step
        for step, day in sorted(days_by_step.items()):
            if days >= day:
                scheduled = (sent_at + timedelta(days=day)).isoformat()
                return f"day {days} since send; step {step} (day {day}) is due", False, (step, scheduled)
        return f"day {days} since send; no follow-up due yet", True, None

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _sent_outreaches(db: Database) -> List[OutreachRecord]:
        return [o for o in db.list_outreach(approval_status="all") if o.send_status == SendStatus.SENT]

    @staticmethod
    def _latest_response(db: Database, outreach_id: str):
        responses = db.list_outreach_responses(outreach_id=outreach_id)
        return responses[0] if responses else None

    @staticmethod
    def _subject(out: OutreachRecord, step: int) -> str:
        base = (out.subject or "").strip()
        return f"Re: {base} (follow-up {step})"

    @staticmethod
    def _default_body(out: OutreachRecord) -> str:
        return (
            f"Hello again{(', ' + out.recipient_name) if out.recipient_name else ''},"
            "\n\nJust checking in on my earlier note. If it is no longer relevant, "
            "one word - 'no' - and you won't hear from me again.\n\nBest regards,"
        )

    @staticmethod
    def _parse_sent_at(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None