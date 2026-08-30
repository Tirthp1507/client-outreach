"""Offline sample-data research provider for local E2E / playground runs.

This is explicitly NOT a live research engine (Jim owns the safe-fetch
ResearchProvider for Phase C). The records here are synthetic design-fixtures
used so the analyst -> scorer -> demo -> outreach chain can be exercised
end-to-end offline. They are named generically and must never be used as real
prospect outreach input.

Register with::

    ResearchRegistry.register("static_sample", StaticResearchProvider())
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from b2b.models import (
    BusinessRecord,
    BusinessResearch,
    EvidenceCategory,
    SourceType,
)
from b2b.research import BaseResearchProvider, EvidenceCollector, ResearchRegistry

logger = logging.getLogger(__name__)

SYNTHETIC_NOTE = "SYNTHETIC FIXTURE - sample research data for offline testing only."

# --- Synthetic sample businesses (hypothetical, generically named) --------
SAMPLE_BUSINESSES: List[Dict] = [
    {
        "name": "Apex Dental Clinic", "category": "clinic", "city": "Ahmedabad",
        "state": "Gujarat", "website": "https://apexdental.example", "email": "care@apexdental.example",
    },
    {
        "name": "Urban Roots Salon", "category": "salon", "city": "Mumbai",
        "state": "Maharashtra", "website": "https://urbanroots.example", "email": "hello@urbanroots.example",
    },
    {
        "name": "Spice & Grain Restaurant", "category": "restaurant", "city": "Pune",
        "state": "Maharashtra", "website": "https://spicegrain.example", "email": "orders@spicegrain.example",
    },
    {
        "name": "Nexus Coaching Institute", "category": "coaching", "city": "Bangalore",
        "state": "Karnataka", "website": "https://nexuscoaching.example", "email": "info@nexuscoaching.example",
    },
    {
        "name": "GreenLeaf Physiotherapy", "category": "clinic", "city": "Chennai",
        "state": "Tamil Nadu", "website": None, "email": "contact@greenleaf.example",
    },
    {
        "name": "FreshCart Grocery Store", "category": "retail", "city": "Delhi",
        "state": "Delhi", "website": "https://freshcart.example", "email": "freshcart@example.com",
    },
]


def _slug(text: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in text).strip("_")[:28]


def sample_business_records() -> List[BusinessRecord]:
    """Build BusinessRecord objects from the synthetic sample dataset."""
    records: List[BusinessRecord] = []
    for i, row in enumerate(SAMPLE_BUSINESSES, start=1):
        slug = _slug(row["name"])
        domain = row["website"].replace("https://", "").rstrip("/") if row["website"] else None
        records.append(BusinessRecord(
            id=f"biz_sample_{slug}",
            name=row["name"],
            category=row["category"],
            city=row["city"],
            state=row["state"],
            website=row["website"],
            domain=domain,
            email=row["email"],
            source_provider="static_sample",
            source_id=f"fixture:{i}",
        ))
    return records


class StaticResearchProvider(BaseResearchProvider):
    """Builds BusinessResearch fixtures from the synthetic dataset by name/domain match."""

    name = "static_sample"

    def __init__(self, datasets: Optional[List[BusinessResearch]] = None) -> None:
        #: caller-supplied research w/ evidence; falls back to generated fixtures.
        self.datasets = datasets or list(generate_sample_research())

    def research(self, business: BusinessRecord, **kwargs) -> BusinessResearch:
        for research in self.datasets:
            if research.business_id == business.id:
                return research
        raise ValueError(f"static_sample provider has no fixture for business {business.id!r}")


def generate_sample_research() -> List[BusinessResearch]:
    """Produce complete fixture research (evidence + weaknesses) per sample business."""
    out: List[BusinessResearch] = []
    for biz in sample_business_records():
        col = EvidenceCollector(biz.id)
        if biz.category == "clinic" and "Dental" in biz.name:
            col.add_fact(EvidenceCategory.SERVICES, "Lists root canal, whitening and orthodontics services",
                         evidence_url=biz.website, source_type=SourceType.WEBSITE_SERVICES)
            col.add_fact(EvidenceCategory.BOOKING_FLOW,
                         "No online appointment booking found - contact page offers phone-only booking",
                         evidence_url=biz.website, source_type=SourceType.WEBSITE_CONTACT)
            col.add_fact(EvidenceCategory.CONTACT_FLOW, "Primary contact method is a phone number on the contact page",
                         evidence_url=biz.website, source_type=SourceType.WEBSITE_CONTACT)
            research = BusinessResearch(
                business_id=biz.id, website_exists=True, website_url=biz.website,
                is_mobile_friendly=True, contact_methods=["phone"],
                services=["Root Canal", "Whitening", "Orthodontics"],
                booking_system_found=False,
                observed_weaknesses=["Phone-only appointment booking", "No patient reminders"],
                evidence=col.get_all(),
            )
        elif biz.category == "salon":
            col.add_fact(EvidenceCategory.SERVICES, "Offers haircuts, colouring, spa and bridal packages",
                         evidence_url=biz.website, source_type=SourceType.WEBSITE_SERVICES)
            col.add_fact(EvidenceCategory.BOOKING_FLOW,
                         "Collected a phone number on the site; no online stylist booking widget observed",
                         evidence_url=biz.website, source_type=SourceType.WEBSITE_HOMEPAGE)
            col.add_fact(EvidenceCategory.CONTACT_FLOW, "WhatsApp click-to-chat button present on the homepage",
                         evidence_url=biz.website, source_type=SourceType.WEBSITE_HOMEPAGE)
            research = BusinessResearch(
                business_id=biz.id, website_exists=True, website_url=biz.website,
                is_mobile_friendly=False, contact_methods=["phone", "whatsapp"],
                services=["Haircut", "Colouring", "Spa", "Bridal"],
                booking_system_found=False,
                observed_weaknesses=["No online booking", "Not mobile-friendly"],
                evidence=col.get_all(),
            )
        elif biz.category == "restaurant":
            col.add_fact(EvidenceCategory.SERVICES, "Full menu with dine-in, delivery and bulk orders",
                         evidence_url=biz.website, source_type=SourceType.WEBSITE_SERVICES)
            col.add_fact(EvidenceCategory.ORDERING_FLOW,
                         "Menu is displayed as static images; no online ordering or cart flow found",
                         evidence_url=biz.website, source_type=SourceType.WEBSITE_SERVICES)
            col.add_fact(EvidenceCategory.CONTACT_FLOW, "Order-taking happens over a posted phone number",
                         evidence_url=biz.website, source_type=SourceType.WEBSITE_CONTACT)
            research = BusinessResearch(
                business_id=biz.id, website_exists=True, website_url=biz.website,
                is_mobile_friendly=True, contact_methods=["phone"],
                services=["Dine-in", "Delivery", "Bulk orders"],
                booking_system_found=False, ordering_system_found=False,
                observed_weaknesses=["No online ordering", "Static menu images"],
                evidence=col.get_all(),
            )
        elif biz.category == "coaching":
            col.add_fact(EvidenceCategory.SERVICES, "JEE/NEET batches, weekend crash courses and mock tests",
                         evidence_url=biz.website, source_type=SourceType.WEBSITE_SERVICES)
            col.add_fact(EvidenceCategory.CONTACT_FLOW,
                         "Site is a static brochure - no inquiry or demo-class registration form found",
                         evidence_url=biz.website, source_type=SourceType.WEBSITE_HOMEPAGE)
            research = BusinessResearch(
                business_id=biz.id, website_exists=True, website_url=biz.website,
                is_mobile_friendly=True, contact_methods=["phone"],
                services=["JEE", "NEET", "Crash courses", "Mock tests"],
                booking_system_found=False,
                observed_weaknesses=["No lead-capture form", "Enquiries depend on phone calls"],
                evidence=col.get_all(),
            )
        elif biz.category == "retail":
            col.add_fact(EvidenceCategory.SERVICES, "Grocery staples, fresh produce and home delivery",
                         source_type=SourceType.WEBSITE_HOMEPAGE)
            col.add_unknown(EvidenceCategory.ORDERING_FLOW, "No online ordering channel observed - phone guide only")
            research = BusinessResearch(
                business_id=biz.id, website_exists=False, website_url=None,
                is_mobile_friendly=None, contact_methods=["phone"],
                services=["Groceries", "Fresh produce", "Home delivery"],
                booking_system_found=False, ordering_system_found=False,
                observed_weaknesses=["No online presence found"],
                evidence=col.get_all(),
            )
        else:
            # business with no productive signal - the analyst MUST NOT manufacture an opportunity.
            research = BusinessResearch(
                business_id=biz.id, website_exists=False, website_url=None,
                is_mobile_friendly=None, contact_methods=[],
                booking_system_found=False, ordering_system_found=False,
                observed_weaknesses=[],
                evidence=[],
            )
        out.append(research)
    return out


# Register so the pipeline's run_research_step can pick it up for local runs.
ResearchRegistry.register("static_sample", StaticResearchProvider())


def build_sample_business_dataset(db) -> None:
    """Persist the synthetic sample businesses + research into a Database."""
    from b2b.models import BusinessStatus
    for biz in sample_business_records():
        existing = db.get_business(biz.id)
        if existing is None:
            db.save_business(biz)
    for research in generate_sample_research():
        db.save_business_research(research)
        db.update_business_status(research.business_id, BusinessStatus.RESEARCHED)