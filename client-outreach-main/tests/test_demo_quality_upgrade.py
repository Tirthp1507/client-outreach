"""Tests for Demo Website Quality Upgrade, Realistic Imagery, Interactivity, and Quality Scoring."""

import html
from pathlib import Path
import pytest
from b2b.demo_generator import DemoBlueprint, DemoGenerator, DemoStrategy
from b2b.fixtures import sample_business_records, generate_sample_research
from b2b.models import (
    BusinessRecord,
    DemoRecord,
    DemoStatus,
    DemoType,
    OpportunityRecord,
    OpportunityType,
    VerticalType,
)
from b2b.quality import DemoQualityChecker


@pytest.fixture
def temp_demo_dir(tmp_path):
    return tmp_path / "demos"


def test_demo_generator_across_all_verticals(temp_demo_dir):
    """Test demo generation for clinic, restaurant, salon, coaching, and retail businesses."""
    generator = DemoGenerator(output_dir=temp_demo_dir)
    checker = DemoQualityChecker(pass_threshold=75.0)

    sample_businesses = sample_business_records()
    assert len(sample_businesses) >= 5

    for biz in sample_businesses:
        opp = OpportunityRecord(
            id=f"opp_{biz.id}",
            business_id=biz.id,
            opportunity_type=OpportunityType.ONLINE_BOOKING if biz.category in ("clinic", "salon", "coaching") else OpportunityType.ORDERING_SYSTEM,
            title=f"Automated Booking & Digital Portal for {biz.name}",
            score=82.0,
            confidence=0.9,
            problem_summary="Manual telephone and walk-in reliance without instant online booking or ordering.",
            proposed_solution="Modern, mobile-first commercial web app with instant booking and WhatsApp checkout.",
            business_value="Capture 3x more bookings and eliminate front-desk bottlenecks.",
        )

        demo = generator.generate(biz, opp)
        assert demo.status == DemoStatus.READY
        assert demo.artifact_path is not None

        artifact_file = temp_demo_dir / demo.id / "index.html"
        assert artifact_file.exists()

        html_content = artifact_file.read_text(encoding="utf-8")

        # 1. Semantic Structure
        assert "<header" in html_content
        assert "<nav" in html_content
        assert "<main" in html_content
        assert "<section" in html_content
        assert "<footer" in html_content

        # 2. Viewport & Mobile Meta
        assert 'name="viewport"' in html_content

        # 3. Personalization
        assert (biz.name in html_content) or (html.escape(biz.name) in html_content)
        assert biz.city in html_content
        if biz.phone:
            assert "".join(c for c in biz.phone if c.isdigit()) in html_content

        # 4. Realistic Visual Content (Images)
        assert html_content.count("<img") >= 4
        assert "alt=" in html_content

        # 5. Interactivity & Dynamic Scripts
        assert "<script" in html_content
        assert "showToast" in html_content
        assert "openModal" in html_content
        assert "wa.me" in html_content

        # 6. Mobile Experience
        assert "mobile-drawer" in html_content
        assert "mobile-sticky-bar" in html_content

        # 7. No Placeholder / Lorem Ipsum
        assert "lorem ipsum" not in html_content.lower()
        assert "placeholder text" not in html_content.lower()
        assert "coming soon" not in html_content.lower()

        # 8. QA Quality Check
        qa = checker.check(demo, artifact_root=Path(temp_demo_dir).parent.parent)
        assert qa.passed is True, f"Demo {demo.id} failed QA for {biz.name}: {qa.issues}"
        assert qa.score >= 85.0


def test_demo_quality_checker_catches_flaws(tmp_path):
    """Ensure DemoQualityChecker penalizes broken, sparse, or placeholder pages."""
    checker = DemoQualityChecker(pass_threshold=75.0)

    # Test 1: Placeholder lorem ipsum content
    bad_dir = tmp_path / "bad_demo"
    bad_dir.mkdir(parents=True)
    bad_file = bad_dir / "index.html"
    bad_file.write_text("""<!DOCTYPE html>
    <html>
    <head><title>Bad Demo</title><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body>
      <header><nav>Nav</nav></header>
      <main>
        <section>
          <h1>Bad Clinic</h1>
          <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>
          <img src="test.jpg" alt="test">
        </section>
      </main>
      <footer>Footer</footer>
      <script>function test(){}</script>
    </body>
    </html>""", encoding="utf-8")

    bad_demo = DemoRecord(
        id="bad_demo",
        opportunity_id="opp_1",
        business_id="biz_1",
        vertical=VerticalType.CLINIC,
        demo_type=DemoType.BOOKING_WEBSITE,
        title="Bad Demo",
        artifact_path=str(bad_file),
        preview_url="/demos/bad_demo/index.html",
        status=DemoStatus.READY,
    )

    qa_bad = checker.check(bad_demo)
    assert qa_bad.passed is False
    assert any("Placeholder content detected" in issue for issue in qa_bad.issues)
    assert any("Page content is suspiciously sparse" in issue for issue in qa_bad.issues)
    assert any("Insufficient visual imagery" in issue for issue in qa_bad.issues)


def test_restaurant_menu_and_cart_interactivity(temp_demo_dir):
    """Test restaurant-specific interactive ordering and cart calculations."""
    generator = DemoGenerator(output_dir=temp_demo_dir)
    biz = BusinessRecord(
        id="biz_rest_1",
        name="Royal Flavors Dining",
        category="restaurant",
        city="Pune",
        state="Maharashtra",
        phone="+91 98220 99999",
        address="10, FC Road, Pune",
    )
    opp = OpportunityRecord(
        id="opp_rest_1",
        business_id=biz.id,
        opportunity_type=OpportunityType.ORDERING_SYSTEM,
        title="Direct Online Ordering & Table Booking",
        score=85.0,
        problem_summary="No online ordering.",
        proposed_solution="Interactive menu + WhatsApp cart.",
        business_value="Save 25% aggregator commissions with direct WhatsApp orders.",
    )

    demo = generator.generate(biz, opp)
    html_content = (temp_demo_dir / demo.id / "index.html").read_text(encoding="utf-8")

    assert "addToCart" in html_content
    assert "renderCart" in html_content
    assert "openOrderCheckoutModal" in html_content
    assert "Reserve a Table" in html_content
    assert "GST (5%)" in html_content
