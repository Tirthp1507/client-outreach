"""Tests for B2B core models, enums, evidence contracts, and serialization."""

import pytest
from b2b.models import (
    ApprovalStatus,
    BusinessRecord,
    BusinessResearch,
    BusinessStatus,
    ClaimType,
    DemoRecord,
    DemoStatus,
    DemoType,
    EvidenceCategory,
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
    SourceType,
    VerticalType,
)


def test_business_record_defaults():
    b = BusinessRecord(
        id="biz_test_1",
        name="Apex Dental Clinic",
        category="clinic",
        city="Ahmedabad",
        website="https://apexdental.in",
        domain="apexdental.in",
    )
    assert b.status == BusinessStatus.DISCOVERED
    assert b.country == "India"
    assert b.created_at is not None
    assert b.updated_at is not None


def test_research_evidence_validation():
    ev = ResearchEvidence(
        id="ev_test_1",
        business_id="biz_test_1",
        category=EvidenceCategory.BOOKING_FLOW,
        claim="No online appointment booking form found on homepage or contact page",
        claim_type=ClaimType.VERIFIED_FACT,
        evidence_url="https://apexdental.in/contact",
        raw_snippet="Call us at 9876543210 for appointment bookings.",
        confidence=1.0,
    )
    assert ev.category == EvidenceCategory.BOOKING_FLOW
    assert ev.claim_type == ClaimType.VERIFIED_FACT
    assert ev.confidence == 1.0


def test_business_research_composition():
    ev1 = ResearchEvidence(
        id="ev_1",
        business_id="biz_test_1",
        category=EvidenceCategory.SERVICES,
        claim="Offers root canal, teeth whitening, orthodontics",
        claim_type=ClaimType.VERIFIED_FACT,
        evidence_url="https://apexdental.in/services",
    )
    res = BusinessResearch(
        business_id="biz_test_1",
        website_exists=True,
        website_url="https://apexdental.in",
        is_mobile_friendly=True,
        services=["Root Canal", "Teeth Whitening", "Orthodontics"],
        booking_system_found=False,
        observed_weaknesses=["Manual telephone booking only", "No WhatsApp chat link"],
        evidence=[ev1],
    )
    assert len(res.evidence) == 1
    assert res.booking_system_found is False
    assert "Root Canal" in res.services


def test_opportunity_record_bounds():
    opp = OpportunityRecord(
        id="opp_test_1",
        business_id="biz_test_1",
        opportunity_type=OpportunityType.ONLINE_BOOKING,
        title="Automated Dental Appointment Booking Web App",
        problem_summary="Patients cannot book or reschedule appointments outside business hours.",
        proposed_solution="Mobile-first booking portal with real-time doctor availability and SMS/WhatsApp confirmation.",
        business_value="Capture 30%+ more appointments and eliminate phone receptionist friction.",
        score=88.5,
        score_reasons=["No existing booking system", "High value per appointment", "Strong local search presence"],
        risks=["Clinic may already use an unlinked third-party software"],
        priority=OpportunityPriority.HIGH,
        qualification_status=QualificationStatus.QUALIFIED,
    )
    assert opp.score == 88.5
    assert opp.priority == OpportunityPriority.HIGH
    assert opp.qualification_status == QualificationStatus.QUALIFIED


def test_demo_and_outreach_records():
    demo = DemoRecord(
        id="demo_test_1",
        opportunity_id="opp_test_1",
        business_id="biz_test_1",
        vertical=VerticalType.CLINIC,
        demo_type=DemoType.BOOKING_WEBSITE,
        title="Apex Dental Interactive Booking Demo",
        artifact_path="output/demos/demo_test_1/index.html",
        preview_url="http://127.0.0.1:8080/demos/demo_test_1",
    )
    assert demo.status == DemoStatus.READY

    outreach = OutreachRecord(
        id="out_test_1",
        business_id="biz_test_1",
        opportunity_id="opp_test_1",
        demo_id="demo_test_1",
        recipient_email="contact@apexdental.in",
        recipient_name="Dr. Patel",
        subject="Quick idea for Apex Dental Clinic online booking",
        body_text="Hi Dr. Patel, I noticed patients can currently only book via phone...",
        approval_status=ApprovalStatus.PENDING_REVIEW,
        send_status=SendStatus.DRAFT,
    )
    assert outreach.approval_status == ApprovalStatus.PENDING_REVIEW
    assert outreach.send_status == SendStatus.DRAFT