"""Tests for B2B SQLite tables, relationships, constraints, and CRUD methods."""

from db.database import Database
from b2b.models import (
    ApprovalStatus,
    BusinessRecord,
    BusinessResearch,
    BusinessStatus,
    ClaimType,
    DemoRecord,
    DemoType,
    EvidenceCategory,
    FollowUpRecord,
    FollowUpStatus,
    OpportunityPriority,
    OpportunityRecord,
    OpportunityType,
    OutreachRecord,
    OutreachResponse,
    QualificationStatus,
    ReplyStatus,
    ResearchEvidence,
    ResponseClassification,
    SendStatus,
    VerticalType,
)


def test_business_crud(tmp_path):
    db = Database(tmp_path / "test_b2b.db")

    biz = BusinessRecord(
        id="biz_ahmedabad_1",
        name="Royal Spice Restaurant",
        category="restaurant",
        city="Ahmedabad",
        state="Gujarat",
        website="https://royalspice.in",
        domain="royalspice.in",
        phone="9876543210",
        email="info@royalspice.in",
    )
    db.save_business(biz)

    # Fetch by ID
    fetched = db.get_business("biz_ahmedabad_1")
    assert fetched is not None
    assert fetched.name == "Royal Spice Restaurant"
    assert fetched.city == "Ahmedabad"
    assert fetched.domain == "royalspice.in"
    assert fetched.status == BusinessStatus.DISCOVERED

    # Fetch by domain
    by_dom = db.get_business_by_domain("royalspice.in")
    assert by_dom is not None
    assert by_dom.id == "biz_ahmedabad_1"

    # Update status
    updated = db.update_business_status("biz_ahmedabad_1", BusinessStatus.RESEARCHED)
    assert updated.status == BusinessStatus.RESEARCHED

    # List with filter
    results = db.list_businesses(category="restaurant", city="Ahmedabad")
    assert len(results) == 1
    assert results[0].id == "biz_ahmedabad_1"


def test_evidence_and_research_crud(tmp_path):
    db = Database(tmp_path / "test_b2b.db")

    biz = BusinessRecord(
        id="biz_2",
        name="FitZone Gym",
        category="gym",
        city="Bangalore",
        domain="fitzonebangalore.com",
    )
    db.save_business(biz)

    ev1 = ResearchEvidence(
        id="ev_fit_1",
        business_id="biz_2",
        category=EvidenceCategory.TECH_STACK,
        claim="Uses WordPress with outdated theme and broken mobile menu",
        claim_type=ClaimType.VERIFIED_FACT,
        evidence_url="https://fitzonebangalore.com",
    )
    ev2 = ResearchEvidence(
        id="ev_fit_2",
        business_id="biz_2",
        category=EvidenceCategory.CONTACT_FLOW,
        claim="Has active WhatsApp click-to-chat button on homepage",
        claim_type=ClaimType.VERIFIED_FACT,
        evidence_url="https://fitzonebangalore.com",
    )

    research = BusinessResearch(
        business_id="biz_2",
        website_exists=True,
        website_url="https://fitzonebangalore.com",
        tech_stack=["WordPress", "jQuery"],
        services=["Personal Training", "CrossFit", "Zumba"],
        contact_methods=["phone", "whatsapp"],
        booking_system_found=False,
        observed_weaknesses=["Broken mobile menu", "No online membership checkout"],
        evidence=[ev1, ev2],
    )
    db.save_business_research(research)

    fetched_res = db.get_business_research("biz_2")
    assert fetched_res is not None
    assert fetched_res.website_exists is True
    assert len(fetched_res.evidence) == 2
    assert "CrossFit" in fetched_res.services


def test_opportunity_and_demo_crud(tmp_path):
    db = Database(tmp_path / "test_b2b.db")

    biz = BusinessRecord(id="biz_3", name="Galaxy Salon", category="salon", city="Mumbai")
    db.save_business(biz)

    opp = OpportunityRecord(
        id="opp_3",
        business_id="biz_3",
        opportunity_type=OpportunityType.ONLINE_BOOKING,
        title="Salon Appointment & Stylist Booking Web App",
        problem_summary="Client has to call or DM on Instagram for appointments.",
        proposed_solution="Instant mobile booking page with service add-ons and stylist calendar.",
        business_value="Reduces missed appointments and DM lag.",
        score=91.0,
        score_reasons=["High footfall", "No online scheduler"],
        priority=OpportunityPriority.HIGH,
    )
    db.save_opportunity(opp)

    fetched_opp = db.get_opportunity("opp_3")
    assert fetched_opp is not None
    assert fetched_opp.score == 91.0

    demo = DemoRecord(
        id="demo_3",
        opportunity_id="opp_3",
        business_id="biz_3",
        vertical=VerticalType.SALON,
        demo_type=DemoType.BOOKING_WEBSITE,
        title="Galaxy Salon Booking Prototype",
        artifact_path="output/demos/demo_3/index.html",
        preview_url="http://127.0.0.1:8080/demos/demo_3",
    )
    db.save_demo(demo)

    fetched_demo = db.get_demo("demo_3")
    assert fetched_demo is not None
    assert fetched_demo.vertical == VerticalType.SALON


def test_outreach_and_approval_flow(tmp_path):
    db = Database(tmp_path / "test_b2b.db")

    biz = BusinessRecord(id="biz_4", name="Elite Coaching", category="coaching", city="Delhi")
    db.save_business(biz)
    opp = OpportunityRecord(
        id="opp_4",
        business_id="biz_4",
        opportunity_type=OpportunityType.LEAD_CAPTURE,
        title="Student Inquiry & Demo Class Portal",
        problem_summary="Static brochure website with no student inquiry capture flow.",
        proposed_solution="Interactive demo class booking & course syllabus download portal.",
        business_value="Double inbound student conversion.",
        score=86.0,
    )
    db.save_opportunity(opp)

    outreach = OutreachRecord(
        id="out_4",
        business_id="biz_4",
        opportunity_id="opp_4",
        recipient_email="director@elitecoaching.in",
        recipient_name="Mr. Sharma",
        subject="Student demo class registration idea for Elite Coaching",
        body_text="Hi Mr. Sharma, noticed prospective students currently have to call...",
        approval_status=ApprovalStatus.PENDING_REVIEW,
        send_status=SendStatus.DRAFT,
    )
    db.save_outreach(outreach)

    # Initial state
    assert db.get_outreach("out_4").approval_status == ApprovalStatus.PENDING_REVIEW

    # Approve
    db.update_outreach_approval("out_4", ApprovalStatus.APPROVED)
    assert db.get_outreach("out_4").approval_status == ApprovalStatus.APPROVED

    # Mark Sent
    db.update_outreach_send_status(
        "out_4",
        SendStatus.SENT,
        sent_at="2026-08-30T10:00:00Z",
        provider_message_id="msg_gmail_12345",
    )
    sent_record = db.get_outreach("out_4")
    assert sent_record.send_status == SendStatus.SENT
    assert sent_record.provider_message_id == "msg_gmail_12345"

    # Inbound response
    resp = OutreachResponse(
        id="resp_4",
        outreach_id="out_4",
        business_id="biz_4",
        classification=ResponseClassification.INTERESTED,
        raw_content="Yes, we would like to see how this works. Can we talk tomorrow?",
        suggested_reply="Hi Mr. Sharma, I would be happy to show you. How does 3 PM work?",
        reply_status=ReplyStatus.PENDING_REVIEW,
    )
    db.save_outreach_response(resp)

    responses = db.list_outreach_responses(business_id="biz_4")
    assert len(responses) == 1
    assert responses[0].classification == ResponseClassification.INTERESTED


def test_followups_crud(tmp_path):
    db = Database(tmp_path / "test_b2b.db")

    biz = BusinessRecord(id="biz_5", name="Apex Salon", category="salon", city="Ahmedabad")
    db.save_business(biz)
    opp = OpportunityRecord(
        id="opp_5",
        business_id="biz_5",
        opportunity_type=OpportunityType.ONLINE_BOOKING,
        title="Salon Booking",
        problem_summary="No booking system",
        proposed_solution="Web app",
        business_value="Higher retention",
        score=88.0,
    )
    db.save_opportunity(opp)
    outreach = OutreachRecord(
        id="out_5",
        business_id="biz_5",
        opportunity_id="opp_5",
        recipient_email="owner@apexsalon.in",
        subject="Booking idea",
        body_text="Hi",
    )
    db.save_outreach(outreach)

    # 1. Create FollowUpRecord
    fu1 = FollowUpRecord(
        id="fu_5_1",
        outreach_id="out_5",
        business_id="biz_5",
        step_number=1,
        scheduled_date="2026-09-02",
        subject="Quick follow-up on booking demo for Apex Salon",
        body_text="Hi, following up on our previous note with a short demo...",
        status=FollowUpStatus.PENDING_REVIEW,
    )
    db.save_followup(fu1)

    fu2 = FollowUpRecord(
        id="fu_5_2",
        outreach_id="out_5",
        business_id="biz_5",
        step_number=2,
        scheduled_date="2026-09-06",
        subject="Final check-in on Apex Salon prototype",
        body_text="Hi, just checking if you had a chance to test...",
        status=FollowUpStatus.PENDING_REVIEW,
    )
    db.save_followup(fu2)

    # 2. Get by ID
    fetched_fu = db.get_followup("fu_5_1")
    assert fetched_fu is not None
    assert fetched_fu.step_number == 1
    assert fetched_fu.status == FollowUpStatus.PENDING_REVIEW

    # 3. List by outreach / business
    fu_list = db.list_followups(outreach_id="out_5")
    assert len(fu_list) == 2
    assert fu_list[0].id == "fu_5_1"
    assert fu_list[1].id == "fu_5_2"

    # 4. Update status
    updated = db.update_followup_status(
        "fu_5_1",
        FollowUpStatus.SENT,
        sent_at="2026-09-02T10:00:00Z",
        provider_message_id="msg_fu_111",
    )
    assert updated is not None
    assert updated.status == FollowUpStatus.SENT
    assert updated.provider_message_id == "msg_fu_111"

    # 5. Response classifications: UNSUBSCRIBED and WRONG_CONTACT
    resp_unsub = OutreachResponse(
        id="resp_5_unsub",
        outreach_id="out_5",
        business_id="biz_5",
        classification=ResponseClassification.UNSUBSCRIBED,
        raw_content="Please unsubscribe me from this mailing list.",
    )
    db.save_outreach_response(resp_unsub)

    resp_wrong = OutreachResponse(
        id="resp_5_wrong",
        outreach_id="out_5",
        business_id="biz_5",
        classification=ResponseClassification.WRONG_CONTACT,
        raw_content="Wrong email, please contact management directly.",
    )
    db.save_outreach_response(resp_wrong)

    all_resps = db.list_outreach_responses(business_id="biz_5")
    assert len(all_resps) == 2
    class_set = {r.classification for r in all_resps}
    assert ResponseClassification.UNSUBSCRIBED in class_set
    assert ResponseClassification.WRONG_CONTACT in class_set