"""Core Data Models for B2B Business Acquisition Automation.

Defines the entity schemas, evidence contracts, opportunity structures,
demo records, outreach packages, and approval/sending state machines.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# --- State Machine & Classification Enums ---

class BusinessStatus(str, Enum):
    DISCOVERED = "discovered"
    RESEARCHING = "researching"
    RESEARCHED = "researched"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    SCORED = "scored"
    DEMO_READY = "demo_ready"
    OUTREACH_READY = "outreach_ready"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SENT = "sent"
    REPLIED = "replied"
    REJECTED = "rejected"
    CLOSED = "closed"


class ClaimType(str, Enum):
    VERIFIED_FACT = "verified_fact"
    AI_INFERENCE = "ai_inference"
    UNKNOWN = "unknown"


class EvidenceCategory(str, Enum):
    IDENTITY = "identity"
    SERVICES = "services"
    TECH_STACK = "tech_stack"
    CONTACT_FLOW = "contact_flow"
    BOOKING_FLOW = "booking_flow"
    ORDERING_FLOW = "ordering_flow"
    MOBILE_UX = "mobile_ux"
    SOCIAL_PRESENCE = "social_presence"
    REPUTATION = "reputation"


class SourceType(str, Enum):
    WEBSITE_HOMEPAGE = "website_homepage"
    WEBSITE_CONTACT = "website_contact"
    WEBSITE_BOOKING = "website_booking"
    WEBSITE_SERVICES = "website_services"
    SOCIAL_PROFILE = "social_profile"
    DIRECTORY_LISTING = "directory_listing"
    DNS_HEADERS = "dns_headers"
    MANUAL_INPUT = "manual_input"


class OpportunityType(str, Enum):
    ONLINE_BOOKING = "online_booking"
    LEAD_CAPTURE = "lead_capture"
    WEBSITE_MODERNIZATION = "website_modernization"
    CUSTOMER_PORTAL = "customer_portal"
    ORDERING_SYSTEM = "ordering_system"
    WHATSAPP_AUTOMATION = "whatsapp_automation"
    CUSTOM_WEBAPP = "custom_webapp"


class OpportunityPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class QualificationStatus(str, Enum):
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    REVIEW_NEEDED = "review_needed"


class VerticalType(str, Enum):
    RESTAURANT = "restaurant"
    SALON = "salon"
    CLINIC = "clinic"
    GYM = "gym"
    COACHING = "coaching"
    RETAIL = "retail"
    REAL_ESTATE = "real_estate"
    HOTEL = "hotel"
    AUTOMOTIVE = "automotive"
    PROFESSIONAL_SERVICES = "professional_services"
    GENERAL_SMB = "general_smb"


class DemoType(str, Enum):
    BOOKING_WEBSITE = "booking_website"
    LANDING_PAGE = "landing_page"
    QUOTATION_PORTAL = "quotation_portal"
    ORDERING_SYSTEM = "ordering_system"
    WORKFLOW_MOCKUP = "workflow_mockup"
    DASHBOARD_PROTO = "dashboard_proto"


class DemoStatus(str, Enum):
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class ApprovalStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class SendStatus(str, Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"


class ResponseClassification(str, Enum):
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    QUESTION = "question"
    WANTS_PRICING = "wants_pricing"
    WANTS_MEETING = "wants_meeting"
    OUT_OF_OFFICE = "out_of_office"
    UNSUBSCRIBED = "unsubscribed"
    WRONG_CONTACT = "wrong_contact"
    BOUNCED = "bounced"
    UNCLEAR = "unclear"


class ReplyStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SENT = "sent"
    DISMISSED = "dismissed"


class FollowUpStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SENT = "sent"
    CANCELLED = "cancelled"
    SUPPRESSED = "suppressed"


# --- Core Entities ---

class ResearchEvidence(BaseModel):
    """Atomic verifiable evidence unit supporting business research & claims."""
    id: str
    business_id: str
    category: EvidenceCategory
    claim: str
    claim_type: ClaimType = ClaimType.VERIFIED_FACT
    evidence_url: Optional[str] = None
    raw_snippet: Optional[str] = None
    source_type: SourceType = SourceType.WEBSITE_HOMEPAGE
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    collected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BusinessResearch(BaseModel):
    """Structured synthesis of all public research and observations for a business."""
    business_id: str
    website_exists: bool = False
    website_url: Optional[str] = None
    is_mobile_friendly: Optional[bool] = None
    speed_score: Optional[float] = None
    tech_stack: List[str] = Field(default_factory=list)
    services: List[str] = Field(default_factory=list)
    pricing_info: Optional[str] = None
    contact_methods: List[str] = Field(default_factory=list)
    social_links: Dict[str, str] = Field(default_factory=dict)
    booking_system_found: bool = False
    ordering_system_found: bool = False
    observed_weaknesses: List[str] = Field(default_factory=list)
    observed_strengths: List[str] = Field(default_factory=list)
    evidence: List[ResearchEvidence] = Field(default_factory=list)
    researched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BusinessRecord(BaseModel):
    """Core business identity and lifecycle record."""
    id: str
    name: str
    category: str
    city: str
    state: Optional[str] = None
    country: str = "India"
    address: Optional[str] = None
    website: Optional[str] = None
    domain: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    source_provider: str = "manual_input"
    source_id: Optional[str] = None
    status: BusinessStatus = BusinessStatus.DISCOVERED
    is_validated: bool = False
    validation_score: float = 0.0
    validation_details: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OpportunityRecord(BaseModel):
    """Structured technology opportunity identified for a business."""
    id: str
    business_id: str
    opportunity_type: OpportunityType
    title: str
    problem_summary: str
    proposed_solution: str
    business_value: str
    score: float = Field(ge=0.0, le=100.0)
    score_reasons: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    priority: OpportunityPriority = OpportunityPriority.MEDIUM
    qualification_status: QualificationStatus = QualificationStatus.QUALIFIED
    evidence_ids: List[str] = Field(default_factory=list)
    status: str = "identified"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class DemoRecord(BaseModel):
    """Interactive prototype demo generated for an opportunity."""
    id: str
    opportunity_id: str
    business_id: str
    vertical: VerticalType = VerticalType.GENERAL_SMB
    demo_type: DemoType = DemoType.LANDING_PAGE
    title: str
    artifact_path: str
    preview_url: Optional[str] = None
    status: DemoStatus = DemoStatus.READY
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OutreachRecord(BaseModel):
    """Personalized outreach copy, approval state, and email dispatch record."""
    id: str
    business_id: str
    opportunity_id: str
    demo_id: Optional[str] = None
    recipient_email: str
    recipient_name: Optional[str] = None
    subject: str
    body_text: str
    body_html: Optional[str] = None
    followup_body: Optional[str] = None
    personalization_reasons: List[str] = Field(default_factory=list)
    evidence_used: List[str] = Field(default_factory=list)
    approval_status: ApprovalStatus = ApprovalStatus.PENDING_REVIEW
    send_status: SendStatus = SendStatus.DRAFT
    sent_at: Optional[str] = None
    provider_message_id: Optional[str] = None
    last_error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OutreachResponse(BaseModel):
    """Inbound reply tracking and AI classification."""
    id: str
    outreach_id: str
    business_id: str
    received_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    classification: ResponseClassification = ResponseClassification.UNCLEAR
    raw_content: str
    suggested_reply: Optional[str] = None
    reply_status: ReplyStatus = ReplyStatus.PENDING_REVIEW


class FollowUpRecord(BaseModel):
    """Multi-step cadence follow-up draft and tracking record."""
    id: str
    outreach_id: str
    business_id: str
    step_number: int = 1
    scheduled_date: Optional[str] = None
    subject: str
    body_text: str
    body_html: Optional[str] = None
    status: FollowUpStatus = FollowUpStatus.PENDING_REVIEW
    sent_at: Optional[str] = None
    provider_message_id: Optional[str] = None
    last_error: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())