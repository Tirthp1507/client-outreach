"""Tests for Ryan's intelligence slice: analyst, scoring, demo, outreach,
classification, follow-up, feedback, quality, and the end-to-end pipeline."""

from datetime import datetime, timedelta, timezone

from b2b.analyst import BusinessAnalyst
from b2b.feedback import OutreachFeedbackEngine
from b2b.fixtures import build_sample_business_dataset
from b2b.followup import FollowUpIntelligence, FollowUpPolicy
from b2b.pipeline import BusinessIntelligenceService
from b2b.quality import DemoQualityChecker, OutreachQualityChecker
from b2b.response_classifier import ResponseClassification, ResponseClassifier
from b2b.scoring import OpportunityScorer
from b2b.scheduler_intent import BusinessCycleContext
from b2b.models import (
    ApprovalStatus,
    BusinessStatus,
    OpportunityRecord,
    OpportunityType,
    OutreachRecord,
    QualificationStatus,
    SendStatus,
    VerticalType,
)
from db.database import Database


def _db(tmp_path):
    db = Database(tmp_path / "test.db")
    build_sample_business_dataset(db)
    return db


def _research(db):
    return [
        r for b in db.list_businesses(limit=100)
        if (r := db.get_business_research(b.id))
    ]


def _pipeline_db(tmp_path):
    """Full pipeline run returning (db, svc, ctx, opps, demos, outreach)."""
    db = _db(tmp_path)
    svc = BusinessIntelligenceService(db)
    ctx = BusinessCycleContext(cycle_id="t1")
    opps = svc.run_analysis_step(ctx, _research(db))
    demos = svc.run_demo_step(ctx, opps)
    outreach = svc.run_outreach_step(ctx, demos)
    return db, svc, ctx, opps, demos, outreach


def _mark_sent(db, out: OutreachRecord, days_ago: int = 20) -> OutreachRecord:
    sent_at = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    db.update_outreach_approval(out.id, ApprovalStatus.APPROVED)
    db.update_outreach_send_status(out.id, SendStatus.SENT, sent_at=sent_at)
    return db.get_outreach(out.id)


# ---------------- Analyst ----------------

def test_analyst_insufficient_evidence_gate(tmp_path):
    db = _db(tmp_path)
    svc = BusinessIntelligenceService(db)
    ctx = BusinessCycleContext(cycle_id="gate")
    opps = svc.run_analysis_step(ctx, _research(db))
    insufficient = ctx.stats.get("insufficient_evidence", [])
    # Exactly one fixture business has empty evidence -> exactly one gate hit.
    assert len(insufficient) == 1
    for opp in opps:
        assert opp.qualification_status == QualificationStatus.QUALIFIED


def test_analyst_refuses_without_research(tmp_path):
    db = _db(tmp_path)
    biz = db.list_businesses(limit=1)[0]
    analyst = BusinessAnalyst()
    result = analyst.analyze(biz, None)
    assert result.sufficient_evidence is False
    assert result.insufficient_reason


def test_analyst_evidence_grounding(tmp_path):
    db = _db(tmp_path)
    research = _research(db)[0]
    biz = db.get_business(research.business_id)
    analyst = BusinessAnalyst()
    result = analyst.analyze(biz, research)
    assert result.sufficient_evidence
    assert result.evidence_ids, "qualified analysis must cite evidence"
    assert result.supporting_claims, "qualified analysis must have supporting claims"
    assert result.reasoning, "analysis must be explainable"
    assert result.confidence > 0.0


# ---------------- Scoring ----------------

def _minimal_analysis():
    from b2b.analyst import AnalysisResult
    return AnalysisResult(
        business_id="b_1",
        opportunity_type=OpportunityType.ONLINE_BOOKING,
        title="Online Booking",
        problem_summary="No self-serve booking observed.",
        proposed_solution="Booking page.",
        business_value="More bookings.",
        confidence=0.7,
        implementation_effort="low",
        risks=["none"],
        unknowns=["intent"],
        evidence_ids=["e1"],
        supporting_claims=["No booking flow found"],
        sufficient_evidence=True,
    )


def test_scorer_transparent_dimensions():
    from b2b.models import BusinessRecord
    scorer = OpportunityScorer()
    biz = BusinessRecord(id="b_1", name="Salon", category="salon", city="Surat")
    scored = scorer.score(_minimal_analysis(), biz)
    total = sum(d.points for d in scored.dimensions)
    assert abs(total - scored.score) < 1e-6
    assert 0 <= scored.score <= 100
    assert len(scored.dimensions) == 8
    assert scored.score_reasons, "score must be explainable"
    assert scored.qualification_status == QualificationStatus.QUALIFIED


def test_scorer_neutral_on_unknown():
    from b2b.models import BusinessRecord
    scorer = OpportunityScorer()
    biz = BusinessRecord(id="b_2", name="Unknown", category="general_smb", city="Delhi")
    scored = scorer.score(_minimal_analysis(), biz)
    for d in scored.dimensions:
        assert 0 <= d.points <= d.max_points
    assert 0 <= scored.score <= 100


def test_scorer_returns_none_for_insufficient():
    from b2b.analyst import AnalysisResult
    from b2b.models import BusinessRecord
    scorer = OpportunityScorer()
    biz = BusinessRecord(id="b_3", name="X", category="other", city="Mumbai")
    weak = AnalysisResult(business_id="b_3", sufficient_evidence=False)
    assert scorer.score(weak, biz) is None


# ---------------- Demo generation ----------------

def test_demo_generation_artifacts(tmp_path):
    _, _, _, opps, demos, _ = _pipeline_db(tmp_path)
    assert len(demos) == len(opps) > 0
    qa = DemoQualityChecker()
    for d in demos:
        assert qa.check(d).passed, "demo must pass quality gate"
        assert d.artifact_path.endswith(".html")
        assert d.preview_url or d.artifact_path  # a location is recorded


# ---------------- Outreach ----------------

def test_outreach_traceability_and_pending_review(tmp_path):
    _, _, _, _, _, outreach = _pipeline_db(tmp_path)
    assert outreach
    qa = OutreachQualityChecker()
    for o in outreach:
        assert o.personalization_reasons, "every draft needs personalization reasons"
        assert o.evidence_used, "every draft must cite evidence"
        assert o.followup_body, "every draft must carry a follow-up body template"
        assert o.approval_status == ApprovalStatus.PENDING_REVIEW
        assert qa.check(o).passed, "draft must pass quality gate"
        assert "{{" not in o.body_text and "@@" not in o.body_text


def test_outreach_gatekeeper_blocks_drafts(tmp_path):
    _, _, _, _, _, outreach = _pipeline_db(tmp_path)
    from b2b.gatekeeper import OutreachGatekeeper
    gate = OutreachGatekeeper()
    for o in outreach:
        can_send, _ = gate.can_send(o)
        assert can_send is False  # nothing leaves without human approval


# ---------------- Classification ----------------

def test_classifier_signal_detection():
    c = ResponseClassifier()
    assert c.classify("Please unsubscribe me").classification == ResponseClassification.UNSUBSCRIBED
    assert c.classify("Please unsubscribe me").suppression_signal
    assert c.classify("Wrong person, please stop mailing us").classification == ResponseClassification.WRONG_CONTACT
    assert c.classify("Wrong person, please stop mailing us").suppression_signal
    r3 = c.classify("Sounds interesting, can we meet tomorrow?")
    assert r3.classification in (ResponseClassification.WANTS_MEETING, ResponseClassification.INTERESTED)
    assert not r3.suppression_signal
    assert c.classify("").classification == ResponseClassification.UNCLEAR
    assert c.classify("Completely random text here").classification == ResponseClassification.UNCLEAR


def test_classifier_suggested_replies():
    c = ResponseClassifier()
    out = OutreachRecord(
        id="o1",
        business_id="b1",
        opportunity_id="opp1",
        recipient_email="x@y.in",
        subject="S",
        body_text="B",
    )
    assert c.suggest_reply("unsub", ResponseClassification.UNSUBSCRIBED, out)
    assert c.suggest_reply("wrong", ResponseClassification.WRONG_CONTACT, out)
    assert c.suggest_reply("ooo", ResponseClassification.OUT_OF_OFFICE, out) is None
    assert c.suggest_reply("x", ResponseClassification.NOT_INTERESTED, out)


# ---------------- Follow-up intelligence ----------------

def _seed_sent_outreach(db, days_ago=20):
    svc = BusinessIntelligenceService(db)
    ctx = BusinessCycleContext(cycle_id="seed")
    for research in _research(db):
        opps = svc.run_analysis_step(ctx, [research])
        if not opps:
            continue
        demo = svc.run_demo_step(ctx, opps[:1])[0]
        out = svc.run_outreach_step(ctx, [demo])[0]
        return _mark_sent(db, out, days_ago)
    raise AssertionError("no analyzed opportunity available to seed a sent outreach")


def test_followup_stages_due_step(tmp_path):
    db = _db(tmp_path)
    out = _seed_sent_outreach(db, days_ago=20)
    fui = FollowUpIntelligence()
    staged, plans = fui.plan_and_stage(db)
    due = [p for p in plans if p.eligible and p.outreach_id == out.id]
    assert due, "20 days after send, a follow-up should be due"
    assert any(f.outreach_id == out.id for f in staged)
    row = db.list_followups(outreach_id=out.id)
    assert row and row[0].status.value == "pending_review"
    assert row[0].step_number == due[0].step


def test_followup_not_staged_for_fresh_send(tmp_path):
    db = _db(tmp_path)
    _seed_sent_outreach(db, days_ago=1)
    fui = FollowUpIntelligence()
    staged, plans = fui.plan_and_stage(db)
    assert not staged


def test_followup_dedup_no_double_staging(tmp_path):
    db = _db(tmp_path)
    _seed_sent_outreach(db, days_ago=20)
    fui = FollowUpIntelligence()
    first, _ = fui.plan_and_stage(db)
    second, _ = fui.plan_and_stage(db)
    assert first
    assert len(second) < len(first)


def test_followup_suppressed_on_unsubscribe(tmp_path):
    db = _db(tmp_path)
    out = _seed_sent_outreach(db, days_ago=20)
    svc = BusinessIntelligenceService(db)
    ctx = BusinessCycleContext(cycle_id="sup")
    svc.ingest_response(ctx, out.id, "Please unsubscribe me")
    fui = FollowUpIntelligence()
    staged, plans = fui.plan_and_stage(db)
    assert not [p for p in plans if p.eligible and p.outreach_id == out.id]
    assert not [f for f in staged if f.outreach_id == out.id]


def test_followup_max_reached(tmp_path):
    db = _db(tmp_path)
    out = _seed_sent_outreach(db, days_ago=30)
    fui = FollowUpIntelligence()
    fui.plan_and_stage(db, FollowUpPolicy(max_followups=1))
    fui.plan_and_stage(db, FollowUpPolicy(max_followups=1))
    staged, plans = fui.plan_and_stage(db, FollowUpPolicy(max_followups=1))
    assert not [p for p in plans if p.eligible and p.outreach_id == out.id]
    assert not [f for f in staged if f.outreach_id == out.id]


# ---------------- Feedback ----------------

def test_feedback_neutral_when_nothing_sent(tmp_path):
    db, svc, ctx, opps, demos, outreach = _pipeline_db(tmp_path)
    report = OutreachFeedbackEngine().learn(db)
    assert report.totals_sent == 0
    assert report.findings == []


def test_feedback_recommends_after_samples(tmp_path):
    db = _db(tmp_path)
    svc = BusinessIntelligenceService(db)
    ctx = BusinessCycleContext(cycle_id="fb")
    opps = svc.run_analysis_step(ctx, _research(db))
    demos = svc.run_demo_step(ctx, opps)
    outreach = svc.run_outreach_step(ctx, demos)
    # Send everything; reply positively to exactly the first five threads.
    for o in outreach:
        _mark_sent(db, o, days_ago=30)
    for o in outreach[:5]:
        svc.ingest_response(ctx, o.id, "Sounds interesting, tell me more")
    fx = OutreachFeedbackEngine()
    report = fx.learn(db)
    assert report.totals_sent == len(outreach) >= 5
    assert report.baseline_reply_rate == 0.5
    assert report.findings, "with 5+ samples a finding per bucket is expected"
    assert any(f.reliable and f.recommendation for f in report.findings)


# ---------------- Pipeline integration ----------------

def test_pipeline_round_trip_stats(tmp_path):
    db, svc, ctx, opps, demos, outreach = _pipeline_db(tmp_path)
    assert ctx.stats["opportunities"] == len(opps)
    assert ctx.stats["demos"] == len(demos)
    assert ctx.stats["outreach_drafts"] == len(outreach)
    assert all(p.approval_status == ApprovalStatus.PENDING_REVIEW for p in outreach)
    assert ctx.stats.get("demos_skipped_below_floor", []) == []
    # Nothing sent yet -> nothing classified, nothing staged, feedback empty.
    assert ctx.stats.get("responses_processed", 0) == 0
    assert "followups_staged" not in ctx.stats


def test_pipeline_ingest_response_updates_status(tmp_path):
    db, svc, ctx, opps, demos, outreach = _pipeline_db(tmp_path)
    out = outreach[0]
    resp = svc.ingest_response(ctx, out.id, "Sounds great, want to see the demo")
    assert resp.classification == ResponseClassification.INTERESTED
    assert resp.suggested_reply
    saved = db.list_outreach_responses(outreach_id=out.id)
    assert saved[0].id == resp.id
    assert db.get_business(out.business_id).status == BusinessStatus.REPLIED