"""Approval Workflow and Outreach Sending Safety Gatekeeper.

Enforces human-in-the-loop approval before any email or message can be dispatched.
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

from b2b.models import ApprovalStatus, OutreachRecord, SendStatus

logger = logging.getLogger(__name__)


class ApprovalGateError(Exception):
    """Raised when an action violates human approval or safety policies."""
    pass


class OutreachGatekeeper:
    """Enforces strict approval state checks and content safety before dispatch."""

    @staticmethod
    def validate_email_address(email: str) -> bool:
        """Simple RFC-compliant email syntax check."""
        if not email or "@" not in email:
            return False
        pattern = r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email.strip()))

    def can_send(self, outreach: OutreachRecord) -> Tuple[bool, str]:
        """Check whether an outreach record is eligible for dispatch."""
        # 1. Mandatory Human Approval Check
        if outreach.approval_status != ApprovalStatus.APPROVED:
            return False, (
                f"Approval Gate Violation: Outreach {outreach.id} is in status "
                f"'{outreach.approval_status.value.upper()}'. Explicit human approval is required."
            )

        # 2. Valid Recipient Email
        if not self.validate_email_address(outreach.recipient_email):
            return False, f"Invalid recipient email address: '{outreach.recipient_email}'"

        # 3. Non-Empty Copy
        if not outreach.subject or not outreach.subject.strip():
            return False, "Outreach subject is missing or empty"
        if not outreach.body_text or not outreach.body_text.strip():
            return False, "Outreach body text is missing or empty"

        # 4. Duplicate Prevention (cannot re-send already SENT outreach)
        if outreach.send_status == SendStatus.SENT:
            return False, f"Outreach {outreach.id} has already been sent at {outreach.sent_at}"

        return True, "Outreach approved and verified for dispatch"

    def assert_sendable(self, outreach: OutreachRecord) -> None:
        """Raise ApprovalGateError if the outreach record cannot be safely sent."""
        allowed, reason = self.can_send(outreach)
        if not allowed:
            raise ApprovalGateError(reason)