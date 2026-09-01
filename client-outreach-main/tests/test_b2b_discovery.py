"""Unit & Integration Tests for Phase B Indian Business Discovery Engine."""

import pytest
from pathlib import Path
from db import Database
from b2b.models import BusinessRecord, BusinessStatus
from b2b.discovery import (
    clean_domain,
    clean_phone,
    BusinessDeduplicator,
    CSVLeadDiscoveryProvider,
    ManualLeadDiscoveryProvider,
    DiscoveryRegistry,
    DiscoveryService,
)
from cli import main


def test_clean_domain_variations():
    assert clean_domain("https://www.apexdental.in/contact?ref=1") == "apexdental.in"
    assert clean_domain("http://clinic.mumbai.org:8080/home") == "clinic.mumbai.org"
    assert clean_domain("radiancehealth.co.in") == "radiancehealth.co.in"
    assert clean_domain("www.oasis-skin.com/") == "oasis-skin.com"
    assert clean_domain(None) is None
    assert clean_domain("") is None


def test_clean_phone_indian_formats():
    assert clean_phone("+91 98250 12345") == "9825012345"
    assert clean_phone("09825012345") == "9825012345"
    assert clean_phone("+91-98250-12345") == "9825012345"
    assert clean_phone("9825012345") == "9825012345"
    assert clean_phone("079-26851234") == "7926851234"
    assert clean_phone(None) is None
    assert clean_phone("123") is None  # too short


def test_csv_provider_parsing_with_aliases(tmp_path):
    csv_file = tmp_path / "leads.csv"
    csv_file.write_text(
        "business_name,vertical,location_address,town,state,homepage,contact_number,mail\n"
        "Apex Care Clinic,clinic,Bodakdev,Ahmedabad,Gujarat,https://apexcare.in,+91 98250 99999,info@apexcare.in\n"
        "Glow Salon,salon,Linking Road,Mumbai,Maharashtra,https://glowsalon.com,9820011111,hi@glowsalon.com\n",
        encoding="utf-8",
    )
    provider = CSVLeadDiscoveryProvider()
    leads = provider.discover(file_path=csv_file)
    assert len(leads) == 2

    assert leads[0].name == "Apex Care Clinic"
    assert leads[0].category == "clinic"
    assert leads[0].city == "Ahmedabad"
    assert leads[0].domain == "apexcare.in"
    assert leads[0].phone == "9825099999"
    assert leads[0].email == "info@apexcare.in"

    assert leads[1].name == "Glow Salon"
    assert leads[1].city == "Mumbai"


def test_csv_provider_filtering(tmp_path):
    csv_file = tmp_path / "leads.csv"
    csv_file.write_text(
        "name,category,city,website\n"
        "Lead A,clinic,Ahmedabad,https://a.in\n"
        "Lead B,salon,Ahmedabad,https://b.in\n"
        "Lead C,clinic,Mumbai,https://c.in\n",
        encoding="utf-8",
    )
    provider = CSVLeadDiscoveryProvider()

    # Filter city
    ahmedabad_leads = provider.discover(file_path=csv_file, city="Ahmedabad")
    assert len(ahmedabad_leads) == 2

    # Filter category
    clinic_leads = provider.discover(file_path=csv_file, category="clinic")
    assert len(clinic_leads) == 2

    # Filter both
    both_leads = provider.discover(file_path=csv_file, city="Ahmedabad", category="clinic")
    assert len(both_leads) == 1
    assert both_leads[0].name == "Lead A"


def test_manual_provider():
    provider = ManualLeadDiscoveryProvider()
    leads = provider.discover(
        name="Apex Dental Clinic",
        city="Ahmedabad",
        category="clinic",
        website="https://apexdental.in",
        phone="+91 98250 12345",
        email="contact@apexdental.in",
    )
    assert len(leads) == 1
    assert leads[0].name == "Apex Dental Clinic"
    assert leads[0].city == "Ahmedabad"
    assert leads[0].domain == "apexdental.in"
    assert leads[0].source_provider == "manual_input"


def test_discovery_registry():
    assert "csv" in DiscoveryRegistry.list_providers()
    assert "manual" in DiscoveryRegistry.list_providers()
    assert isinstance(DiscoveryRegistry.get("csv"), CSVLeadDiscoveryProvider)
    assert isinstance(DiscoveryRegistry.get("manual"), ManualLeadDiscoveryProvider)


def test_discovery_service_ingest_and_deduplication(tmp_path):
    db_path = tmp_path / "test_disc.db"
    db = Database(db_path)
    service = DiscoveryService(db=db)

    csv_file = tmp_path / "leads_sample.csv"
    csv_file.write_text(
        "name,category,city,website,phone\n"
        "Apex Dental Clinic,clinic,Ahmedabad,https://apexdental.in,9825012345\n"
        "Oasis Skin Clinic,clinic,Mumbai,https://oasisskin.com,9820045678\n"
        "Apex Dental Centre,clinic,Ahmedabad,https://apexdental.in,9825012345\n"  # Domain duplicate
        "Apex Dental,clinic,Ahmedabad,https://differentapex.in,9825012345\n",     # Fuzzy name duplicate in Ahmedabad
        encoding="utf-8",
    )

    res = service.ingest_leads("csv", file_path=csv_file)
    assert res.total_discovered == 4
    assert res.total_saved == 2
    assert res.total_duplicates == 2

    # Check database records
    businesses = db.list_businesses()
    assert len(businesses) == 2
    names = {b.name for b in businesses}
    assert "Apex Dental Clinic" in names
    assert "Oasis Skin Clinic" in names

    # Re-running same file should detect all as duplicates
    res2 = service.ingest_leads("csv", file_path=csv_file)
    assert res2.total_saved == 0
    assert res2.total_duplicates == 4


def test_cli_discover_and_leads_commands(tmp_path):
    db_path = tmp_path / "test_cli.db"
    csv_file = tmp_path / "cli_leads.csv"
    csv_file.write_text(
        "name,category,city,website,phone,email\n"
        "Sunrise Hospital,clinic,Ahmedabad,https://sunriseahmedabad.in,+91 98250 11111,info@sunriseahmedabad.in\n"
        "Zenith Fitness Arena,gym,Pune,https://zenithfitness.in,+91 98220 22222,join@zenithfitness.in\n",
        encoding="utf-8",
    )

    # Run discover CLI
    exit_code = main(["discover", "--output-dir", str(tmp_path), "--file", str(csv_file)])
    assert exit_code == 0

    # Verify DB has leads
    db = Database(tmp_path / "automation.db")
    leads = db.list_businesses()
    assert len(leads) == 2

    # Run leads CLI
    exit_leads = main(["leads", "--output-dir", str(tmp_path)])
    assert exit_leads == 0

    # Run add-lead CLI
    exit_add = main([
        "add-lead",
        "--output-dir", str(tmp_path),
        "--name", "Radiance Spa",
        "--city", "Bengaluru",
        "--category", "salon",
        "--website", "https://radiancespa.in",
    ])
    assert exit_add == 0

    # Check updated total
    assert len(db.list_businesses()) == 3
