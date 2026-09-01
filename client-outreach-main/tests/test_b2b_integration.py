"""Full-lifecycle B2B integration tests using Jim's real modules.

Covers the acceptance flow at the data level (mock/dry-run email so no real
dispatch): discovery-seeded business -> research -> AI analyst -> score ->
demo -> outreach (PENDING_REVIEW) -> APPROVE -> gate-checked SEND via
OutreachSendingService (+ ConsoleEmailProvider staged payload) -> persisted
send_state -> response ingest -> classification -> follow-up staging/approve/
send -> unsub trigger suppression -> feedback report. Every step persists to
SQLite through db/database.py.
"""

from datetime import datetime, timedelta, timezone

from b2b.email_provider import ConsoleEmailProvider, OutreachSendingService
from b2b.feedback import OutreachFeedbackEngine
from b2b.fixtures import build_sample_business_dataset
from b2b.followup import FollowUpIntelligence
from b2b.gatekeeper import ApprovalGateError
from b2b.pipeline import BusinessIntelligenceService
from b2b.scheduler_intent import BusinessCycleContext
from b2b.models import (
    ApprovalStatus,
    BusinessStatus,
    FollowUpStatus,
    ResponseClassification,
    SendStatus,
)
from db.database import Database


class FailingEmailProvider(ConsoleEmailProvider):
    """Deliberately failing provider to verify failed sends are persisted."""

    def send_email(self, **kwargs):
        raise RuntimeError("simulated SMTP outage")


def _db(tmp_path):
    db = Database(tmp_path / "integ.db")
    build_sample_business_dataset(db)
    return db


def _research(db):
    return [
        r for b in db.list_businesses(limit=100)
        if (r := db.get_business_research(b.id))
    ]


def _run_cycle(db):
    svc = BusinessIntelligenceService(db)
    ctx = BusinessCycleContext(cycle_id="integ")
    opps = svc.run_analysis_step(ctx, _research(db))
    demos = svc.run_demo_step(ctx, opps)
    outreach = svc.run_outreach_step(ctx, demos)
    return svc, ctx, opps, demos, outreach


def _approve_send(db, out, days_ago=0):
    db.update_outreach_approval(out.id, ApprovalStatus.APPROVED)
    send_svc = OutreachSendingService(db, provider=ConsoleEmailProvider(), live=False)
    now = datetime.now(timezone.utc)
    sent_at = (now - timedelta(days=days_ago)).isoformat()
    db.update_outreach_send_status(out.id, SendStatus.SENT, sent_at=sent_at)
    return db.get_outreach(out.id)


def test_approval_gate_blocks_unapproved_send(tmp_path):
    db = _db(tmp_path)
    _, _, _, _, outreach = _run_cycle(db)
    out = next(o for o in outreach if o.recipient_email)
    send_svc = OutreachSendingService(db, provider=ConsoleEmailProvider(), live=False)
    try:
        send_svc.send_outreach(out.id)
        assert False, "unapproved outreach must never send"
    except ApprovalGateError:
        pass
    assert db.get_outreach(out.id).send_status == SendStatus.DRAFT


def test_mock_send_persists_result_and_staged_payload(tmp_path):
    db = _db(tmp_path)
    send_svc = OutreachSendingService(db, provider=ConsoleEmailProvider(), live=False)
    _, _, _, _, outreach = _run_cycle(db)
    out = next(o for o in outreach if o.recipient_email)
    db.update_outreach_approval(out.id, ApprovalStatus.APPROVED)

    updated = send_svc.send_outreach(out.id)
    assert updated.send_status == SendStatus.SENT
    assert updated.provider_message_id
    assert updated.sent_at
    assert updated.provider_message_id.startswith("mock_msg_")
    assert db.get_business(out.business_id).status == BusinessStatus.SENT

    staged = db.stage / "outreach_staged" if False else None  # payload lands under PROJECT_ROOT/output
    from config import PROJECT_ROOT
    payloads = list((PROJECT_ROOT / "output" / "outreach_staged").glob("*.json"))
    assert payloads, "dry-run send must persist a staged payload for audit"
    payload_text = payloads[-1].read_text(encoding="utf-8")
    assert '"delivered_mock"' in payload_text


def test_failed_send_persists_error_state(tmp_path):
    db = _db(tmp_path)
    _, _, _, _, outreach = _run_cycle(db)
    out = next(o for o in outreach if o.recipient_email)
    db.update_outreach_approval(out.id, ApprovalStatus.APPROVED)

    # live=True so the injected failing provider isn't overridden by dry-run;
    # simulated outage must persist to SQLite as FAILED (never faked as success).
    send_svc = OutreachSendingService(db, provider=FailingEmailProvider(), live=True)
    try:
        send_svc.send_outreach(out.id)
        assert False, "failing provider should raise"
    except RuntimeError:
        pass
    failed = db.get_outreach(out.id)
    assert failed.send_status == SendStatus.FAILED
    assert "outage" in (failed.last_error or "")


def test_response_ingest_classification_and_followup_suppression(tmp_path):
    db = _db(tmp_path)
    svc, ctx, opps, demos, outreach = _run_cycle(db)
    out = _approve_send(db, next(o for o in outreach if o.recipient_email), days_ago=20)

    resp = svc.ingest_response(ctx, out.id, "Please unsubscribe me")
    assert resp.classification == ResponseClassification.UNSUBSCRIBED
    assert db.get_business(out.business_id).status == BusinessStatus.REPLIED

    fui = FollowUpIntelligence()
    staged, plans = fui.plan_and_stage(db)
    assert not [p for p in plans if p.eligible and p.outreach_id == out.id]
    assert not [f for f in staged if f.outreach_id == out.id]


def test_followup_approve_and_mock_send(tmp_path):
    db = _db(tmp_path)
    svc, ctx, opps, demos, outreach = _run_cycle(db)
    out = _approve_send(db, next(o for o in outreach if o.recipient_email), days_ago=20)

    fui = FollowUpIntelligence()
    staged, _ = fui.plan_and_stage(db)
    assert staged, "a due follow-up must be staged"

    followup = db.list_followups(outreach_id=out.id)[0]
    assert followup.status == FollowUpStatus.PENDING_REVIEW

    db.update_followup_status(followup.id, FollowUpStatus.APPROVED)
    send_svc = OutreachSendingService(db, provider=ConsoleEmailProvider(), live=False)
    sent = send_svc.send_followup(followup.id)
    assert sent.status == FollowUpStatus.SENT
    assert sent.sent_at and sent.provider_message_id


def test_followup_requires_approval_before_send(tmp_path):
    db = _db(tmp_path)
    svc, ctx, opps, demos, outreach = _run_cycle(db)
    out = _approve_send(db, next(o for o in outreach if o.recipient_email), days_ago=20)
    fui = FollowUpIntelligence()
    staged, _ = fui.plan_and_stage(db)
    followup = db.list_followups(outreach_id=out.id)[0]
    send_svc = OutreachSendingService(db, provider=ConsoleEmailProvider(), live=False)
    try:
        send_svc.send_followup(followup.id)
        assert False, "unapproved follow-up must never send"
    except ApprovalGateError:
        pass


def test_feedback_persists_and_informs(tmp_path):
    db = _db(tmp_path)
    svc, ctx, opps, demos, outreach = _run_cycle(db)
    for o in outreach[:6]:
        _approve_send(db, o, days_ago=30)
    for o in outreach[:4]:
        svc.ingest_response(ctx, o.id, "Sounds interesting, tell me more")
    fx = OutreachFeedbackEngine()
    report = fx.learn(db)
    assert report.totals_sent >= 6
    assert report.totals_replied >= 4
    assert report.baseline_reply_rate is not None
    assert db.get_outreach(o.id) is not None  # state fully persisted


def test_full_pipeline_all_persisted(tmp_path):
    db = _db(tmp_path)
    svc, ctx, opps, demos, outreach = _run_cycle(db)
    for opp in opps:
        assert db.get_opportunity(opp.id) is not None
    for d in demos:
        assert db.get_demo(d.id) is not None
    for o in outreach:
        assert db.get_outreach(o.id) is not None
        assert o.approval_status == ApprovalStatus.PENDING_REVIEW
    assert ctx.errors == []