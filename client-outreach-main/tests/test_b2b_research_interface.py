"""Tests for B2B Research Provider interface and EvidenceCollector provenance."""

from b2b.models import (
    BusinessRecord,
    BusinessResearch,
    ClaimType,
    EvidenceCategory,
    SourceType,
)
from b2b.research import (
    BaseResearchProvider,
    EvidenceCollector,
    ResearchRegistry,
)


def test_evidence_collector_facts_inferences_unknowns():
    collector = EvidenceCollector("biz_test_99")

    # Add verified fact
    f1 = collector.add_fact(
        category=EvidenceCategory.SERVICES,
        claim="Provides hair spa, facial, manicure",
        evidence_url="https://glowsalon.in/services",
        raw_snippet="Hair Spa: Rs 1500 | Facial: Rs 2000",
        source_type=SourceType.WEBSITE_SERVICES,
        confidence=1.0,
    )
    assert f1.claim_type == ClaimType.VERIFIED_FACT
    assert f1.confidence == 1.0

    # Add inference
    i1 = collector.add_inference(
        category=EvidenceCategory.TECH_STACK,
        claim="Likely custom PHP site based on .php URL extensions and header response",
        evidence_url="https://glowsalon.in/booking.php",
        confidence=0.8,
    )
    assert i1.claim_type == ClaimType.AI_INFERENCE
    assert i1.confidence == 0.8

    # Add unknown
    u1 = collector.add_unknown(
        category=EvidenceCategory.REPUTATION,
        claim="Google Reviews count and rating could not be verified from official public page",
    )
    assert u1.claim_type == ClaimType.UNKNOWN
    assert u1.confidence == 0.0

    assert len(collector.get_all()) == 3
    assert len(collector.get_facts()) == 1
    assert len(collector.get_inferences()) == 1
    assert len(collector.get_unknowns()) == 1


def test_research_registry():
    class MockResearchProvider(BaseResearchProvider):
        name = "mock_research"
        def research(self, business: BusinessRecord, **kwargs) -> BusinessResearch:
            collector = EvidenceCollector(business.id)
            collector.add_fact(
                EvidenceCategory.IDENTITY,
                f"Verified business name '{business.name}' on website footer",
                evidence_url=business.website,
            )
            return BusinessResearch(
                business_id=business.id,
                website_exists=True,
                website_url=business.website,
                evidence=collector.get_all(),
            )

    provider = MockResearchProvider()
    ResearchRegistry.register("mock", provider)
    assert ResearchRegistry.get("mock") is provider

    biz = BusinessRecord(id="b_1", name="Test Biz", category="retail", city="Surat", website="https://testbiz.in")
    res = ResearchRegistry.get("mock").research(biz)
    assert res.business_id == "b_1"
    assert len(res.evidence) == 1
    assert res.evidence[0].claim_type == ClaimType.VERIFIED_FACT