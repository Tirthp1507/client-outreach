"""Tests for B2B Discovery Provider interface, deduplication, and domain/phone normalizers."""

from b2b.discovery import (
    BaseDiscoveryProvider,
    BusinessDeduplicator,
    DiscoveryRegistry,
    clean_domain,
    clean_phone,
)
from b2b.models import BusinessRecord, BusinessStatus


def test_clean_domain():
    assert clean_domain("https://www.drpatelclinic.com/about?ref=g") == "drpatelclinic.com"
    assert clean_domain("http://salon-glow.in/") == "salon-glow.in"
    assert clean_domain("myrestaurant.co.in:8080/menu") == "myrestaurant.co.in"
    assert clean_domain("") is None
    assert clean_domain(None) is None


def test_clean_phone():
    assert clean_phone("+91 98765 43210") == "9876543210"
    assert clean_phone("09876543210") == "9876543210"
    assert clean_phone("+91-79-26543210") == "7926543210"
    assert clean_phone("123") is None
    assert clean_phone(None) is None


def test_business_deduplicator():
    existing = [
        BusinessRecord(
            id="biz_1",
            name="Apex Dental Clinic Pvt Ltd",
            category="clinic",
            city="Ahmedabad",
            domain="apexdental.in",
        ),
        BusinessRecord(
            id="biz_2",
            name="Royal Spice Restaurant",
            category="restaurant",
            city="Mumbai",
            domain="royalspicemumbai.com",
        ),
    ]

    dedup = BusinessDeduplicator(existing)

    # 1. Exact domain match
    cand1 = BusinessRecord(
        id="cand_1",
        name="Apex Smiles",
        category="clinic",
        city="Delhi",
        domain="apexdental.in",
    )
    is_dup, reason = dedup.is_duplicate(cand1)
    assert is_dup is True
    assert "Domain duplicate" in reason

    # 2. Exact normalized name & city match
    cand2 = BusinessRecord(
        id="cand_2",
        name="Apex Dental Clinic",
        category="clinic",
        city="Ahmedabad",
        domain="newapex.in",
    )
    is_dup, reason = dedup.is_duplicate(cand2)
    assert is_dup is True
    assert "Name & City duplicate" in reason

    # 3. New unique business
    cand3 = BusinessRecord(
        id="cand_3",
        name="Ocean Blue Seafood",
        category="restaurant",
        city="Goa",
        domain="oceanbluegoa.in",
    )
    is_dup, reason = dedup.is_duplicate(cand3)
    assert is_dup is False
    assert reason is None

    # Register and verify it now blocks
    dedup.register(cand3)
    is_dup, _ = dedup.is_duplicate(cand3)
    assert is_dup is True


def test_discovery_registry():
    class DummyProvider(BaseDiscoveryProvider):
        name = "dummy_provider"
        def discover(self, **kwargs):
            return [
                BusinessRecord(
                    id="dummy_1",
                    name="Dummy Cafe",
                    category="cafe",
                    city="Pune",
                )
            ]

    provider = DummyProvider()
    DiscoveryRegistry.register("dummy", provider)
    assert DiscoveryRegistry.get("dummy") is provider
    assert "dummy" in DiscoveryRegistry.list_providers()

    leads = DiscoveryRegistry.get("dummy").discover()
    assert len(leads) == 1
    assert leads[0].name == "Dummy Cafe"