"""Tests for OutreachGatekeeper approval enforcement and send validation."""

import pytest
from b2b.gatekeeper import ApprovalGateError, OutreachGatekeeper
from b2b.models import ApprovalStatus, OutreachRecord, SendStatus


def test_gatekeeper_blocks_unapproved_outreach():
    gatekeeper = OutreachGatekeeper()

    # 1. PENDING_REVIEW -> Blocked
    draft = OutreachRecord(
        id="out_draft_1",
        business_id="biz_1",
        opportunity_id="opp_1",
        recipient_email="owner@business.in",
        subject="Idea for business",
        body_text="Hi owner, noticed...",
        approval_status=ApprovalStatus.PENDING_REVIEW,
    )
    can_send, reason = gatekeeper.can_send(draft)
    assert can_send is False
    assert "PENDING_REVIEW" in reason
    with pytest.raises(ApprovalGateError):
        gatekeeper.assert_sendable(draft)

    # 2. REJECTED -> Blocked
    rejected = OutreachRecord(
        id="out_rej_1",
        business_id="biz_1",
        opportunity_id="opp_1",
        recipient_email="owner@business.in",
        subject="Idea for business",
        body_text="Hi owner, noticed...",
        approval_status=ApprovalStatus.REJECTED,
    )
    can_send_rej, reason_rej = gatekeeper.can_send(rejected)
    assert can_send_rej is False
    assert "REJECTED" in reason_rej

    # 3. APPROVED with invalid email -> Blocked
    approved_bad_email = OutreachRecord(
        id="out_app_bad",
        business_id="biz_1",
        opportunity_id="opp_1",
        recipient_email="not-an-email",
        subject="Idea for business",
        body_text="Hi owner, noticed...",
        approval_status=ApprovalStatus.APPROVED,
    )
    can_send_bad, reason_bad = gatekeeper.can_send(approved_bad_email)
    assert can_send_bad is False
    assert "Invalid recipient email" in reason_bad

    # 4. APPROVED with valid email and copy -> Allowed
    approved_valid = OutreachRecord(
        id="out_app_valid",
        business_id="biz_1",
        opportunity_id="opp_1",
        recipient_email="owner@business.in",
        subject="Idea for business",
        body_text="Hi owner, noticed you don't have online booking...",
        approval_status=ApprovalStatus.APPROVED,
        send_status=SendStatus.DRAFT,
    )
    can_send_ok, reason_ok = gatekeeper.can_send(approved_valid)
    assert can_send_ok is True
    gatekeeper.assert_sendable(approved_valid)  # does not raise

    # 5. Already SENT -> Blocked from re-sending
    already_sent = OutreachRecord(
        id="out_sent_1",
        business_id="biz_1",
        opportunity_id="opp_1",
        recipient_email="owner@business.in",
        subject="Idea for business",
        body_text="Hi owner, noticed...",
        approval_status=ApprovalStatus.APPROVED,
        send_status=SendStatus.SENT,
        sent_at="2026-08-30T10:00:00Z",
    )
    can_send_dup, reason_dup = gatekeeper.can_send(already_sent)
    assert can_send_dup is False
    assert "already been sent" in reason_dup