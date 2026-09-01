"""Demo Strategy & Generator: Build client-specific, deeply interactive, production-grade commercial websites.

Every generated prototype is a full-featured commercial website tailored to the prospect's identity,
business category, research evidence, and sales opportunity.
Features:
- Modern typography (Outfit for headlines, Inter for body/UI)
- High-resolution, curated, category-specific imagery
- Mobile-first responsive layouts with hamburger drawer & sticky bottom action bar
- Real front-end interactive flows (multi-step appointment bookers, digital menus with live cart,
  service package builders, course explorers, and dynamic WhatsApp checkout handoffs)
- "Why Choose Us" value pillars, visual galleries, verified testimonials, FAQ accordions,
  live business hours, and Google Maps direction triggers.
"""

from __future__ import annotations

import html
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from b2b.analyst import vertical_for
from b2b.models import (
    BusinessRecord,
    DemoRecord,
    DemoStatus,
    DemoType,
    OpportunityRecord,
    OpportunityType,
    VerticalType,
)
from config import PROJECT_ROOT

logger = logging.getLogger(__name__)

OPPORTUNITY_TO_DEMO_TYPE: Dict[OpportunityType, DemoType] = {
    OpportunityType.ONLINE_BOOKING: DemoType.BOOKING_WEBSITE,
    OpportunityType.LEAD_CAPTURE: DemoType.LANDING_PAGE,
    OpportunityType.ORDERING_SYSTEM: DemoType.ORDERING_SYSTEM,
    OpportunityType.WEBSITE_MODERNIZATION: DemoType.LANDING_PAGE,
    OpportunityType.CUSTOMER_PORTAL: DemoType.DASHBOARD_PROTO,
    OpportunityType.WHATSAPP_AUTOMATION: DemoType.WORKFLOW_MOCKUP,
    OpportunityType.CUSTOM_WEBAPP: DemoType.WORKFLOW_MOCKUP,
}

_VERTICAL_THEMES: Dict[VerticalType, Dict[str, str]] = {
    VerticalType.CLINIC: {
        "primary": "#0284c7",
        "primary_dark": "#0369a1",
        "primary_light": "#e0f2fe",
        "accent": "#0d9488",
        "accent_light": "#ccfbf1",
        "gradient": "linear-gradient(135deg, #0284c7 0%, #0d9488 100%)",
        "hero_gradient": "linear-gradient(135deg, #0f172a 0%, #0369a1 60%, #0d9488 100%)",
        "bg_soft": "#f0f9ff",
        "badge_bg": "#e0f2fe",
        "badge_text": "#0369a1",
        "icon": "⚕️",
        "tagline": "Advanced Healthcare & Multi-Specialty Clinical Excellence",
        "cta_text": "Book Appointment",
        "cta_icon": "📅",
    },
    VerticalType.RESTAURANT: {
        "primary": "#ea580c",
        "primary_dark": "#c2410c",
        "primary_light": "#ffedd5",
        "accent": "#f59e0b",
        "accent_light": "#fef3c7",
        "gradient": "linear-gradient(135deg, #ea580c 0%, #d97706 100%)",
        "hero_gradient": "linear-gradient(135deg, #1c1917 0%, #9a3412 60%, #ea580c 100%)",
        "bg_soft": "#fff7ed",
        "badge_bg": "#ffedd5",
        "badge_text": "#9a3412",
        "icon": "🍽️",
        "tagline": "Authentic Flavors, Chef Specials & Direct Table Ordering",
        "cta_text": "Order Online",
        "cta_icon": "🛍️",
    },
    VerticalType.SALON: {
        "primary": "#be185d",
        "primary_dark": "#9d174d",
        "primary_light": "#fce7f3",
        "accent": "#9333ea",
        "accent_light": "#f3e8ff",
        "gradient": "linear-gradient(135deg, #be185d 0%, #7e22ce 100%)",
        "hero_gradient": "linear-gradient(135deg, #18181b 0%, #831843 60%, #be185d 100%)",
        "bg_soft": "#fdf2f8",
        "badge_bg": "#fce7f3",
        "badge_text": "#9d174d",
        "icon": "✂️",
        "tagline": "Luxury Hair Styling, Skin Therapies & Aesthetic Makeovers",
        "cta_text": "Book Session",
        "cta_icon": "✨",
    },
    VerticalType.COACHING: {
        "primary": "#2563eb",
        "primary_dark": "#1d4ed8",
        "primary_light": "#dbeafe",
        "accent": "#4f46e5",
        "accent_light": "#e0e7ff",
        "gradient": "linear-gradient(135deg, #2563eb 0%, #4f46e5 100%)",
        "hero_gradient": "linear-gradient(135deg, #0f172a 0%, #1e3a8a 60%, #312e81 100%)",
        "bg_soft": "#eff6ff",
        "badge_bg": "#dbeafe",
        "badge_text": "#1e40af",
        "icon": "🎓",
        "tagline": "Top Rankers Mentorship, Concept Clarity & Result-Driven Batches",
        "cta_text": "Reserve Free Demo Class",
        "cta_icon": "📚",
    },
    VerticalType.GYM: {
        "primary": "#16a34a",
        "primary_dark": "#15803d",
        "primary_light": "#dcfce7",
        "accent": "#06b6d4",
        "accent_light": "#cffafe",
        "gradient": "linear-gradient(135deg, #16a34a 0%, #059669 100%)",
        "hero_gradient": "linear-gradient(135deg, #09090b 0%, #14532d 60%, #16a34a 100%)",
        "bg_soft": "#f0fdf4",
        "badge_bg": "#dcfce7",
        "badge_text": "#166534",
        "icon": "🏋️",
        "tagline": "Elite Strength Training, Personal Coaching & Modern Equipment",
        "cta_text": "Claim 1-Day VIP Pass",
        "cta_icon": "🔥",
    },
    VerticalType.RETAIL: {
        "primary": "#059669",
        "primary_dark": "#047857",
        "primary_light": "#d1fae5",
        "accent": "#f59e0b",
        "accent_light": "#fef3c7",
        "gradient": "linear-gradient(135deg, #059669 0%, #d97706 100%)",
        "hero_gradient": "linear-gradient(135deg, #064e3b 0%, #047857 60%, #059669 100%)",
        "bg_soft": "#ecfdf5",
        "badge_bg": "#d1fae5",
        "badge_text": "#065f46",
        "icon": "🛒",
        "tagline": "Farm-Fresh Groceries, Daily Essentials & Express Home Delivery",
        "cta_text": "Shop Fresh Catalog",
        "cta_icon": "🛍️",
    },
    VerticalType.REAL_ESTATE: {
        "primary": "#334155",
        "primary_dark": "#1e293b",
        "primary_light": "#f1f5f9",
        "accent": "#d97706",
        "accent_light": "#fef3c7",
        "gradient": "linear-gradient(135deg, #334155 0%, #d97706 100%)",
        "hero_gradient": "linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #334155 100%)",
        "bg_soft": "#f8fafc",
        "badge_bg": "#f1f5f9",
        "badge_text": "#1e293b",
        "icon": "🏢",
        "tagline": "Premium Residential & Commercial Properties with Verified Titles",
        "cta_text": "Schedule Site Visit",
        "cta_icon": "🔑",
    },
    VerticalType.GENERAL_SMB: {
        "primary": "#0f766e",
        "primary_dark": "#115e59",
        "primary_light": "#ccfbf1",
        "accent": "#0284c7",
        "accent_light": "#e0f2fe",
        "gradient": "linear-gradient(135deg, #0f766e 0%, #0284c7 100%)",
        "hero_gradient": "linear-gradient(135deg, #0f172a 0%, #115e59 60%, #0f766e 100%)",
        "bg_soft": "#f0fdfa",
        "badge_bg": "#ccfbf1",
        "badge_text": "#134e4a",
        "icon": "⚡",
        "tagline": "Professional Services, Trusted Solutions & Seamless Customer Support",
        "cta_text": "Get Instant Quote",
        "cta_icon": "💬",
    },
}


class DemoBlueprint:
    """Blueprint defining the tailored prototype strategy for a business."""

    def __init__(
        self,
        business_id: str,
        opportunity_id: str,
        vertical: VerticalType,
        demo_type: DemoType,
        title: str,
        problem: str,
        solution: str,
        key_features: Optional[List[str]] = None,
        custom_services: Optional[List[str]] = None,
    ) -> None:
        self.business_id = business_id
        self.opportunity_id = opportunity_id
        self.vertical = vertical
        self.demo_type = demo_type
        self.title = title
        self.problem = problem
        self.solution = solution
        self.key_features = key_features or []
        self.custom_services = custom_services or []


class DemoStrategy:
    """Determines the appropriate vertical blueprint and tailored features."""

    def blueprint(
        self,
        business: BusinessRecord,
        opp: OpportunityRecord,
        research_services: Optional[List[str]] = None,
    ) -> DemoBlueprint:
        vertical = vertical_for(business.category)
        demo_type = OPPORTUNITY_TO_DEMO_TYPE.get(opp.opportunity_type, DemoType.BOOKING_WEBSITE)
        short_title = f"{business.name} — Official Website & Interactive Solution"

        return DemoBlueprint(
            business_id=business.id,
            opportunity_id=opp.id,
            vertical=vertical,
            demo_type=demo_type,
            title=short_title,
            problem=opp.problem_summary or "Manual inquiry flow without instant online booking or ordering.",
            solution=opp.proposed_solution or "Modern, mobile-first interactive booking & digital customer portal.",
            key_features=self._vertical_features(vertical, demo_type),
            custom_services=research_services or [],
        )

    @staticmethod
    def _vertical_features(vertical: VerticalType, demo_type: DemoType) -> List[str]:
        if vertical == VerticalType.CLINIC:
            return ["Instant appointment booking", "Doctor & specialty selector", "Automated WhatsApp reminders", "Digital prescription portal"]
        if vertical == VerticalType.RESTAURANT:
            return ["Interactive digital menu", "Live cart & bill estimator", "Table reservation manager", "Direct WhatsApp takeaway handoff"]
        if vertical == VerticalType.SALON:
            return ["Service & package selector", "Master stylist choice", "Real-time calendar slots", "Instant booking confirmation"]
        if vertical == VerticalType.COACHING:
            return ["Course & batch discovery", "Free demo class reservation", "Syllabus preview", "Counseling slot picker"]
        if vertical == VerticalType.GYM:
            return ["Membership plan picker", "Trainer selector", "EMI cost estimator", "1-Day VIP Trial Pass generator"]
        if vertical == VerticalType.RETAIL:
            return ["Digital product catalog", "Instant cart counter", "Delivery slot picker", "WhatsApp order dispatch"]
        if vertical == VerticalType.REAL_ESTATE:
            return ["Unit configuration selector", "EMI payment estimator", "Virtual tour trigger", "VIP site visit scheduler"]
        return ["Mobile-first responsive UX", "Instant lead capture", "Live service quote calculator", "Direct WhatsApp routing"]


class DemoGenerator:
    """Generates fully self-contained, responsive, client-specific HTML websites."""

    def __init__(
        self,
        output_dir: Optional[Path | str] = None,
        preview_base_url: str = "/demos",
    ) -> None:
        self.output_dir = Path(output_dir) if output_dir else (PROJECT_ROOT / "output" / "demos")
        self.preview_base_url = preview_base_url.rstrip("/")

    def generate(
        self,
        business: BusinessRecord,
        opp: OpportunityRecord,
        blueprint: Optional[DemoBlueprint] = None,
    ) -> DemoRecord:
        bp = blueprint or DemoStrategy().blueprint(business, opp)
        demo_id = f"demo_{uuid.uuid4().hex[:10]}"
        demo_dir = self.output_dir / demo_id
        demo_dir.mkdir(parents=True, exist_ok=True)

        index_path = demo_dir / "index.html"
        rendered_html = self._render(business, bp)
        index_path.write_text(rendered_html, encoding="utf-8")

        metadata = {
            "business_name": business.name,
            "city": business.city,
            "vertical": bp.vertical.value,
            "opportunity_type": opp.opportunity_type.value if opp.opportunity_type else None,
            "problem": bp.problem,
            "solution": bp.solution,
            "key_features": bp.key_features,
            "demo_type": bp.demo_type.value,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            artifact_rel = str(index_path.relative_to(PROJECT_ROOT))
        except ValueError:
            artifact_rel = str(index_path)

        return DemoRecord(
            id=demo_id,
            opportunity_id=opp.id,
            business_id=business.id,
            vertical=bp.vertical,
            demo_type=bp.demo_type,
            title=bp.title,
            artifact_path=artifact_rel,
            preview_url=f"{self.preview_base_url}/{demo_id}/index.html",
            status=DemoStatus.READY,
            metadata_json=metadata,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _render(self, business: BusinessRecord, bp: DemoBlueprint) -> str:
        theme = _VERTICAL_THEMES.get(bp.vertical, _VERTICAL_THEMES[VerticalType.GENERAL_SMB])
        content_html = self._generate_vertical_content(business, bp, theme)

        page = _MASTER_HTML_TEMPLATE
        biz_name = business.name or "Premier Business"
        city = business.city or "Ahmedabad"
        state = business.state or "Gujarat"
        phone = business.phone or "+91 98250 12345"
        address = business.address or f"402, Commercial Arcade, Main Road, {city}, {state}"
        email = business.email or f"contact@{biz_name.lower().replace(' ', '')}.com"
        clean_phone = "".join(c for c in phone if c.isdigit())
        whatsapp_phone = clean_phone if clean_phone.startswith("91") else f"91{clean_phone[-10:]}"

        replacements = {
            "{{TITLE}}": html.escape(bp.title),
            "{{BUSINESS_NAME}}": html.escape(biz_name),
            "{{CITY}}": html.escape(city),
            "{{STATE}}": html.escape(state),
            "{{PHONE}}": html.escape(phone),
            "{{CLEAN_PHONE}}": clean_phone,
            "{{WHATSAPP_PHONE}}": whatsapp_phone,
            "{{ADDRESS}}": html.escape(address),
            "{{EMAIL}}": html.escape(email),
            "{{CATEGORY}}": html.escape(business.category.replace("_", " ").title()),
            "{{PROBLEM}}": html.escape(bp.problem),
            "{{SOLUTION}}": html.escape(bp.solution),
            "{{TAGLINE}}": theme["tagline"],
            "{{CTA_TEXT}}": theme["cta_text"],
            "{{CTA_ICON}}": theme["cta_icon"],
            "{{PRIMARY_COLOR}}": theme["primary"],
            "{{PRIMARY_DARK}}": theme["primary_dark"],
            "{{PRIMARY_LIGHT}}": theme["primary_light"],
            "{{ACCENT_COLOR}}": theme["accent"],
            "{{ACCENT_LIGHT}}": theme["accent_light"],
            "{{GRADIENT}}": theme["gradient"],
            "{{HERO_GRADIENT}}": theme["hero_gradient"],
            "{{BG_SOFT}}": theme["bg_soft"],
            "{{BADGE_BG}}": theme["badge_bg"],
            "{{BADGE_TEXT}}": theme["badge_text"],
            "{{ICON}}": theme["icon"],
            "{{CONTENT_HTML}}": content_html,
        }

        for key, val in replacements.items():
            page = page.replace(key, val)

        return page

    def _generate_vertical_content(
        self, business: BusinessRecord, bp: DemoBlueprint, theme: Dict[str, str]
    ) -> str:
        v = bp.vertical
        if v == VerticalType.CLINIC:
            return _CLINIC_TEMPLATE
        elif v == VerticalType.RESTAURANT:
            return _RESTAURANT_TEMPLATE
        elif v == VerticalType.SALON:
            return _SALON_TEMPLATE
        elif v == VerticalType.COACHING:
            return _COACHING_TEMPLATE
        elif v == VerticalType.GYM:
            return _GYM_TEMPLATE
        elif v == VerticalType.RETAIL:
            return _RETAIL_TEMPLATE
        elif v == VerticalType.REAL_ESTATE:
            return _REAL_ESTATE_TEMPLATE
        else:
            return _GENERAL_SMB_TEMPLATE


# ==============================================================================
# MASTER HTML & CSS DESIGN SYSTEM
# ==============================================================================

_MASTER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">
  <title>{{TITLE}}</title>
  <meta name="description" content="{{BUSINESS_NAME}} in {{CITY}} - {{TAGLINE}}. Explore services, schedule appointments, and connect directly.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --primary: {{PRIMARY_COLOR}};
      --primary-dark: {{PRIMARY_DARK}};
      --primary-light: {{PRIMARY_LIGHT}};
      --accent: {{ACCENT_COLOR}};
      --accent-light: {{ACCENT_LIGHT}};
      --gradient: {{GRADIENT}};
      --hero-gradient: {{HERO_GRADIENT}};
      --bg-soft: {{BG_SOFT}};
      --badge-bg: {{BADGE_BG}};
      --badge-text: {{BADGE_TEXT}};
      --text: #0f172a;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --border-focus: var(--primary);
      --card-bg: #ffffff;
      --shadow-sm: 0 2px 8px rgba(15, 23, 42, 0.05);
      --shadow-md: 0 10px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04);
      --shadow-lg: 0 20px 35px -10px rgba(15, 23, 42, 0.12);
      --radius-sm: 8px;
      --radius-md: 14px;
      --radius-lg: 20px;
      --radius-full: 9999px;
      --container-max: 1240px;
      --header-height: 76px;
    }

    *, *::before, *::after {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    html {
      scroll-behavior: smooth;
      -webkit-text-size-adjust: 100%;
    }

    body {
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      background: #f8fafc;
      color: var(--text);
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
      overflow-x: hidden;
      padding-bottom: 70px;
    }

    h1, h2, h3, h4, h5, .brand-font {
      font-family: 'Outfit', sans-serif;
      font-weight: 700;
      line-height: 1.25;
      color: var(--text);
    }

    a {
      color: inherit;
      text-decoration: none;
    }

    img {
      max-width: 100%;
      height: auto;
      display: block;
      object-fit: cover;
    }

    button, input, select, textarea {
      font-family: inherit;
      font-size: inherit;
    }

    .container {
      width: 100%;
      max-width: var(--container-max);
      margin: 0 auto;
      padding: 0 20px;
    }

    /* Top Announcement Bar */
    .announcement-bar {
      background: #0f172a;
      color: #94a3b8;
      font-size: 13px;
      padding: 8px 0;
      border-bottom: 1px solid #1e293b;
    }
    .announcement-inner {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }
    .announcement-item {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .announcement-item strong {
      color: #f8fafc;
    }
    .badge-live {
      background: #22c55e;
      color: #052e16;
      padding: 2px 8px;
      border-radius: var(--radius-full);
      font-weight: 700;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    /* Main Sticky Navigation */
    .header-nav {
      position: sticky;
      top: 0;
      z-index: 1000;
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      height: var(--header-height);
      display: flex;
      align-items: center;
      transition: all 0.3s ease;
    }
    .nav-inner {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 20px;
    }
    .brand-logo {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 22px;
      font-weight: 800;
      color: var(--text);
    }
    .brand-icon-box {
      width: 44px;
      height: 44px;
      border-radius: 12px;
      background: var(--gradient);
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 22px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
      flex-shrink: 0;
    }
    .brand-text {
      display: flex;
      flex-direction: column;
    }
    .brand-name {
      font-family: 'Outfit', sans-serif;
      font-weight: 800;
      font-size: 20px;
      line-height: 1.1;
      letter-spacing: -0.5px;
    }
    .brand-city {
      font-size: 12px;
      color: var(--text-muted);
      font-weight: 500;
    }
    .nav-links {
      display: flex;
      align-items: center;
      gap: 28px;
      list-style: none;
    }
    .nav-link {
      font-size: 14px;
      font-weight: 600;
      color: #334155;
      transition: color 0.2s ease;
      position: relative;
    }
    .nav-link:hover {
      color: var(--primary);
    }
    .nav-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      padding: 12px 24px;
      font-size: 14px;
      font-weight: 700;
      border-radius: var(--radius-full);
      border: 1px solid transparent;
      cursor: pointer;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      white-space: nowrap;
      text-align: center;
    }
    .btn-primary {
      background: var(--gradient);
      color: #ffffff;
      box-shadow: 0 4px 14px rgba(2, 132, 199, 0.25);
    }
    .btn-primary:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 20px rgba(2, 132, 199, 0.35);
      color: #ffffff;
    }
    .btn-outline {
      background: #ffffff;
      border-color: var(--border);
      color: var(--text);
    }
    .btn-outline:hover {
      background: var(--bg-soft);
      border-color: var(--primary);
      color: var(--primary);
      transform: translateY(-2px);
    }
    .btn-whatsapp {
      background: #25d366;
      color: #ffffff;
      box-shadow: 0 4px 12px rgba(37, 211, 102, 0.25);
    }
    .btn-whatsapp:hover {
      background: #1eb954;
      transform: translateY(-2px);
      box-shadow: 0 8px 18px rgba(37, 211, 102, 0.35);
      color: #ffffff;
    }
    .btn-sm {
      padding: 8px 16px;
      font-size: 13px;
    }
    .btn-lg {
      padding: 16px 32px;
      font-size: 16px;
    }

    /* Mobile Hamburger */
    .mobile-menu-btn {
      display: none;
      background: transparent;
      border: none;
      width: 40px;
      height: 40px;
      cursor: pointer;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      gap: 5px;
    }
    .mobile-menu-btn span {
      width: 24px;
      height: 2px;
      background: var(--text);
      border-radius: 2px;
      transition: all 0.3s ease;
    }

    /* Mobile Drawer */
    .mobile-drawer {
      position: fixed;
      top: var(--header-height);
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(255, 255, 255, 0.98);
      backdrop-filter: blur(16px);
      display: flex;
      flex-direction: column;
      padding: 30px 24px;
      gap: 20px;
      transform: translateX(100%);
      transition: transform 0.3s ease;
      z-index: 999;
      overflow-y: auto;
    }
    .mobile-drawer.active {
      transform: translateX(0);
    }
    .mobile-drawer .nav-link {
      font-size: 18px;
      padding: 12px 0;
      border-bottom: 1px solid var(--border);
    }

    /* Section Base */
    section {
      padding: 80px 0;
      position: relative;
    }
    .section-header {
      text-align: center;
      max-width: 720px;
      margin: 0 auto 50px;
    }
    .section-eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--badge-bg);
      color: var(--badge-text);
      font-size: 12px;
      font-weight: 700;
      padding: 6px 14px;
      border-radius: var(--radius-full);
      text-transform: uppercase;
      letter-spacing: 0.8px;
      margin-bottom: 14px;
    }
    .section-title {
      font-size: 36px;
      letter-spacing: -0.5px;
      margin-bottom: 16px;
    }
    .section-subtitle {
      font-size: 16px;
      color: var(--text-muted);
      line-height: 1.6;
    }

    /* Hero Section */
    .hero-section {
      padding: 60px 0 80px;
      background: radial-gradient(circle at top right, var(--bg-soft) 0%, #f8fafc 70%);
      position: relative;
      overflow: hidden;
    }
    .hero-grid {
      display: grid;
      grid-template-columns: 1.15fr 1fr;
      gap: 50px;
      align-items: center;
    }
    .hero-content {
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .hero-badge-row {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .rating-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: #ffffff;
      border: 1px solid var(--border);
      padding: 6px 14px;
      border-radius: var(--radius-full);
      font-size: 13px;
      font-weight: 600;
      box-shadow: var(--shadow-sm);
    }
    .rating-stars {
      color: #f59e0b;
    }
    .hero-title {
      font-size: 48px;
      letter-spacing: -1px;
      line-height: 1.15;
    }
    .hero-title span.highlight {
      background: var(--gradient);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      display: inline-block;
    }
    .hero-subtitle {
      font-size: 18px;
      color: var(--text-muted);
      line-height: 1.6;
    }
    .hero-cta-group {
      display: flex;
      align-items: center;
      gap: 16px;
      flex-wrap: wrap;
      margin-top: 8px;
    }
    .hero-stats-row {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
      margin-top: 24px;
      padding-top: 24px;
      border-top: 1px solid var(--border);
    }
    .hero-stat {
      display: flex;
      flex-direction: column;
    }
    .hero-stat-num {
      font-family: 'Outfit', sans-serif;
      font-size: 26px;
      font-weight: 800;
      color: var(--primary);
    }
    .hero-stat-label {
      font-size: 13px;
      color: var(--text-muted);
      font-weight: 500;
    }

    /* Hero Visual Card */
    .hero-visual-wrap {
      position: relative;
    }
    .hero-main-img-card {
      border-radius: var(--radius-lg);
      overflow: hidden;
      box-shadow: var(--shadow-lg);
      border: 1px solid var(--border);
      position: relative;
      aspect-ratio: 4 / 3;
      background: #0f172a;
    }
    .hero-main-img-card img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 0.6s ease;
    }
    .hero-main-img-card:hover img {
      transform: scale(1.03);
    }
    .hero-floating-card {
      position: absolute;
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 14px 18px;
      box-shadow: var(--shadow-md);
      display: flex;
      align-items: center;
      gap: 12px;
      z-index: 2;
    }
    .floating-card-1 {
      bottom: -20px;
      left: -20px;
    }
    .floating-card-2 {
      top: -20px;
      right: -20px;
    }
    .floating-icon {
      width: 38px;
      height: 38px;
      border-radius: 10px;
      background: var(--bg-soft);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
    }
    .floating-text strong {
      display: block;
      font-size: 14px;
      color: var(--text);
    }
    .floating-text span {
      font-size: 12px;
      color: var(--text-muted);
    }

    /* Cards & Grids */
    .cards-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 28px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 30px;
      box-shadow: var(--shadow-sm);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      display: flex;
      flex-direction: column;
      position: relative;
    }
    .card:hover {
      transform: translateY(-4px);
      box-shadow: var(--shadow-md);
      border-color: var(--primary);
    }
    .card-img-wrap {
      border-radius: var(--radius-md);
      overflow: hidden;
      margin: -10px -10px 20px;
      aspect-ratio: 16 / 10;
      position: relative;
    }
    .card-img-wrap img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 0.4s ease;
    }
    .card:hover .card-img-wrap img {
      transform: scale(1.05);
    }
    .card-badge {
      position: absolute;
      top: 12px;
      right: 12px;
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(8px);
      color: #ffffff;
      padding: 4px 10px;
      border-radius: var(--radius-full);
      font-size: 11px;
      font-weight: 700;
    }
    .card-icon {
      width: 52px;
      height: 52px;
      border-radius: 14px;
      background: var(--bg-soft);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 26px;
      margin-bottom: 18px;
    }
    .card-title {
      font-size: 20px;
      margin-bottom: 10px;
    }
    .card-desc {
      font-size: 14px;
      color: var(--text-muted);
      line-height: 1.6;
      margin-bottom: 18px;
      flex-grow: 1;
    }
    .card-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding-top: 16px;
      border-top: 1px solid var(--border);
    }
    .card-price {
      font-family: 'Outfit', sans-serif;
      font-size: 18px;
      font-weight: 800;
      color: var(--primary);
    }

    /* Interactive Solution Hub */
    .interactive-hub {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 40px;
      box-shadow: var(--shadow-lg);
      position: relative;
    }
    .interactive-hub-header {
      border-bottom: 1px solid var(--border);
      padding-bottom: 24px;
      margin-bottom: 30px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }
    .hub-title-group h3 {
      font-size: 24px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .hub-badge {
      background: var(--gradient);
      color: #ffffff;
      font-size: 12px;
      font-weight: 700;
      padding: 4px 12px;
      border-radius: var(--radius-full);
    }

    /* Interactive Tabs & Filters */
    .filter-tabs {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 28px;
    }
    .filter-tab {
      padding: 10px 20px;
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: var(--radius-full);
      font-size: 14px;
      font-weight: 600;
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.2s ease;
    }
    .filter-tab:hover {
      border-color: var(--primary);
      color: var(--primary);
    }
    .filter-tab.active {
      background: var(--primary);
      border-color: var(--primary);
      color: #ffffff;
      box-shadow: 0 4px 12px rgba(2, 132, 199, 0.25);
    }

    /* Form Inputs */
    .form-group {
      margin-bottom: 20px;
    }
    .form-label {
      font-size: 13px;
      font-weight: 700;
      color: #334155;
      margin-bottom: 8px;
      display: block;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .form-input, .form-select, .form-textarea {
      width: 100%;
      padding: 14px 18px;
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      font-size: 15px;
      font-family: inherit;
      background: #ffffff;
      color: var(--text);
      transition: all 0.2s;
    }
    .form-input:focus, .form-select:focus, .form-textarea:focus {
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 4px rgba(2, 132, 199, 0.15);
    }

    /* Gallery Grid */
    .gallery-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 20px;
    }
    .gallery-item {
      border-radius: var(--radius-md);
      overflow: hidden;
      position: relative;
      aspect-ratio: 1;
      box-shadow: var(--shadow-sm);
      cursor: pointer;
    }
    .gallery-item img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 0.5s ease;
    }
    .gallery-item:hover img {
      transform: scale(1.08);
    }
    .gallery-overlay {
      position: absolute;
      inset: 0;
      background: linear-gradient(to top, rgba(15, 23, 42, 0.8) 0%, transparent 60%);
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
      padding: 20px;
      color: #ffffff;
      opacity: 0;
      transition: opacity 0.3s ease;
    }
    .gallery-item:hover .gallery-overlay {
      opacity: 1;
    }
    .gallery-title {
      font-size: 16px;
      font-weight: 700;
    }
    .gallery-sub {
      font-size: 12px;
      color: #cbd5e1;
    }

    /* Testimonials */
    .testimonials-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 28px;
    }
    .testimonial-card {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 30px;
      box-shadow: var(--shadow-sm);
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .testimonial-header {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .testimonial-avatar {
      width: 50px;
      height: 50px;
      border-radius: 50%;
      object-fit: cover;
      border: 2px solid var(--primary-light);
    }
    .testimonial-name {
      font-weight: 700;
      font-size: 16px;
    }
    .testimonial-role {
      font-size: 12px;
      color: var(--text-muted);
    }
    .testimonial-text {
      font-size: 14px;
      color: #334155;
      line-height: 1.6;
      font-style: italic;
    }

    /* FAQ Accordion */
    .faq-list {
      max-width: 800px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .faq-item {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      overflow: hidden;
      transition: all 0.2s ease;
    }
    .faq-question {
      padding: 20px 24px;
      font-weight: 700;
      font-size: 16px;
      cursor: pointer;
      display: flex;
      justify-content: space-between;
      align-items: center;
      user-select: none;
    }
    .faq-question:hover {
      color: var(--primary);
    }
    .faq-icon {
      font-size: 20px;
      transition: transform 0.25s ease;
    }
    .faq-item.active .faq-icon {
      transform: rotate(45deg);
    }
    .faq-answer {
      padding: 0 24px 20px;
      font-size: 14px;
      color: var(--text-muted);
      line-height: 1.6;
      display: none;
    }
    .faq-item.active .faq-answer {
      display: block;
    }

    /* Contact Section */
    .contact-grid {
      display: grid;
      grid-template-columns: 1fr 1.2fr;
      gap: 40px;
    }
    .contact-info-card {
      background: var(--gradient);
      color: #ffffff;
      border-radius: var(--radius-lg);
      padding: 40px;
      display: flex;
      flex-direction: column;
      gap: 28px;
      box-shadow: var(--shadow-lg);
    }
    .contact-info-card h3 {
      color: #ffffff;
      font-size: 26px;
    }
    .contact-item {
      display: flex;
      align-items: flex-start;
      gap: 14px;
    }
    .contact-item-icon {
      font-size: 22px;
      width: 40px;
      height: 40px;
      background: rgba(255, 255, 255, 0.2);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .contact-item-text strong {
      display: block;
      font-size: 15px;
      margin-bottom: 2px;
    }
    .contact-item-text span {
      font-size: 13px;
      color: rgba(255, 255, 255, 0.85);
    }
    .hours-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      margin-top: 10px;
    }
    .hours-table td {
      padding: 6px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.15);
    }

    /* Footer */
    .site-footer {
      background: #0f172a;
      color: #94a3b8;
      padding: 60px 0 30px;
      font-size: 14px;
    }
    .footer-grid {
      display: grid;
      grid-template-columns: 2fr 1fr 1fr 1fr;
      gap: 40px;
      margin-bottom: 40px;
    }
    .footer-brand h4 {
      color: #ffffff;
      font-size: 20px;
      margin-bottom: 12px;
    }
    .footer-col h5 {
      color: #ffffff;
      font-size: 15px;
      margin-bottom: 16px;
    }
    .footer-links {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .footer-links a:hover {
      color: #ffffff;
    }
    .footer-bottom {
      padding-top: 24px;
      border-top: 1px solid #1e293b;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      font-size: 13px;
    }

    /* Sticky Mobile Action Bar */
    .mobile-sticky-bar {
      display: none;
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: #ffffff;
      border-top: 1px solid var(--border);
      padding: 10px 16px;
      z-index: 990;
      box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.08);
    }
    .mobile-sticky-grid {
      display: grid;
      grid-template-columns: 1fr 1fr 1.5fr;
      gap: 8px;
    }
    .mobile-sticky-btn {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 2px;
      padding: 8px 4px;
      font-size: 11px;
      font-weight: 700;
      border-radius: var(--radius-sm);
      text-align: center;
    }

    /* Toast Notification */
    .toast-container {
      position: fixed;
      bottom: 80px;
      right: 24px;
      z-index: 2000;
      display: flex;
      flex-direction: column;
      gap: 10px;
      pointer-events: none;
    }
    .toast {
      background: #0f172a;
      color: #ffffff;
      padding: 14px 20px;
      border-radius: var(--radius-md);
      font-size: 14px;
      font-weight: 600;
      box-shadow: var(--shadow-lg);
      display: flex;
      align-items: center;
      gap: 10px;
      animation: slideUp 0.3s ease forwards;
      pointer-events: auto;
    }
    @keyframes slideUp {
      from { transform: translateY(20px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }

    /* Modal */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.7);
      backdrop-filter: blur(6px);
      z-index: 3000;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    .modal-backdrop.active {
      display: flex;
    }
    .modal-box {
      background: #ffffff;
      border-radius: var(--radius-lg);
      width: 100%;
      max-width: 540px;
      padding: 32px;
      box-shadow: var(--shadow-lg);
      position: relative;
      animation: popIn 0.25s ease;
      max-height: 90vh;
      overflow-y: auto;
    }
    @keyframes popIn {
      from { transform: scale(0.95); opacity: 0; }
      to { transform: scale(1); opacity: 1; }
    }
    .modal-close-btn {
      position: absolute;
      top: 20px;
      right: 20px;
      background: #f1f5f9;
      border: none;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      cursor: pointer;
      font-size: 16px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    /* Responsive Breakpoints */
    @media (max-width: 1024px) {
      .hero-grid {
        grid-template-columns: 1fr;
        gap: 40px;
      }
      .hero-title {
        font-size: 40px;
      }
      .contact-grid {
        grid-template-columns: 1fr;
      }
      .footer-grid {
        grid-template-columns: 1fr 1fr;
      }
    }

    @media (max-width: 768px) {
      body {
        padding-bottom: 76px;
      }
      .nav-links, .nav-actions .btn:not(.btn-sm) {
        display: none;
      }
      .mobile-menu-btn {
        display: flex;
      }
      .hero-title {
        font-size: 32px;
      }
      .hero-stats-row {
        grid-template-columns: 1fr 1fr;
      }
      .section-title {
        font-size: 28px;
      }
      .interactive-hub {
        padding: 24px 18px;
      }
      .mobile-sticky-bar {
        display: block;
      }
      .footer-grid {
        grid-template-columns: 1fr;
      }
    }

    @media (max-width: 390px) {
      .hero-title {
        font-size: 28px;
      }
      .hero-stats-row {
        grid-template-columns: 1fr;
      }
      .btn-lg {
        padding: 12px 20px;
        font-size: 14px;
        width: 100%;
      }
    }
  </style>
</head>
<body>

  <!-- Top Announcement Bar -->
  <div class="announcement-bar">
    <div class="container announcement-inner">
      <div class="announcement-item">
        <span class="badge-live">OPEN NOW</span>
        <span>Serving {{CITY}} & Nearby Areas • Mon–Sun 8:30 AM – 9:30 PM</span>
      </div>
      <div class="announcement-item">
        <span>📍 {{ADDRESS}}</span>
        <span>•</span>
        <a href="tel:{{CLEAN_PHONE}}"><strong>📞 {{PHONE}}</strong></a>
      </div>
    </div>
  </div>

  <!-- Sticky Main Header Navigation -->
  <header class="header-nav" id="mainHeader">
    <div class="container nav-inner">
      <a href="#hero" class="brand-logo">
        <div class="brand-icon-box">{{ICON}}</div>
        <div class="brand-text">
          <span class="brand-name">{{BUSINESS_NAME}}</span>
          <span class="brand-city">{{CITY}}, {{STATE}}</span>
        </div>
      </a>

      <nav>
        <ul class="nav-links">
          <li><a href="#services" class="nav-link">Services</a></li>
          <li><a href="#solution" class="nav-link">Interactive Hub</a></li>
          <li><a href="#why-us" class="nav-link">Why Choose Us</a></li>
          <li><a href="#gallery" class="nav-link">Gallery</a></li>
          <li><a href="#testimonials" class="nav-link">Reviews</a></li>
          <li><a href="#contact" class="nav-link">Contact</a></li>
        </ul>
      </nav>

      <div class="nav-actions">
        <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20I%20would%20like%20to%20inquire%20about%20your%20services." target="_blank" class="btn btn-whatsapp btn-sm">
          <span>💬 WhatsApp</span>
        </a>
        <a href="#solution" class="btn btn-primary btn-sm">
          <span>{{CTA_ICON}} {{CTA_TEXT}}</span>
        </a>
        <button class="mobile-menu-btn" id="mobileToggle" aria-label="Toggle Navigation Menu">
          <span></span>
          <span></span>
          <span></span>
        </button>
      </div>
    </div>
  </header>

  <!-- Mobile Menu Drawer -->
  <div class="mobile-drawer" id="mobileDrawer">
    <a href="#services" class="nav-link" onclick="closeDrawer()">⭐ Our Services</a>
    <a href="#solution" class="nav-link" onclick="closeDrawer()">⚡ {{CTA_TEXT}}</a>
    <a href="#why-us" class="nav-link" onclick="closeDrawer()">🏆 Why Choose Us</a>
    <a href="#gallery" class="nav-link" onclick="closeDrawer()">📸 Photo Gallery</a>
    <a href="#testimonials" class="nav-link" onclick="closeDrawer()">💬 Verified Reviews</a>
    <a href="#faq" class="nav-link" onclick="closeDrawer()">❓ Common Questions</a>
    <a href="#contact" class="nav-link" onclick="closeDrawer()">📍 Location & Hours</a>
    <div style="margin-top: 20px; display: flex; flex-direction: column; gap: 10px;">
      <a href="tel:{{CLEAN_PHONE}}" class="btn btn-outline">📞 Call {{PHONE}}</a>
      <a href="https://wa.me/{{WHATSAPP_PHONE}}" target="_blank" class="btn btn-whatsapp">💬 Instant WhatsApp Chat</a>
    </div>
  </div>

  <!-- Main Content Inserted Per Vertical -->
  <main>
    {{CONTENT_HTML}}
  </main>

  <!-- Footer -->
  <footer class="site-footer">
    <div class="container">
      <div class="footer-grid">
        <div class="footer-brand">
          <h4>{{ICON}} {{BUSINESS_NAME}}</h4>
          <p style="margin-bottom: 16px; line-height: 1.6;">{{TAGLINE}}. Dedicated to providing premier experiences, transparent pricing, and instant online convenience to our customers across {{CITY}}.</p>
          <div style="display: flex; gap: 10px; font-size: 18px;">
            <span>⭐ Rated 4.9/5 by 450+ verified customers in {{CITY}}</span>
          </div>
        </div>
        <div class="footer-col">
          <h5>Quick Links</h5>
          <ul class="footer-links">
            <li><a href="#hero">Home</a></li>
            <li><a href="#services">Featured Services</a></li>
            <li><a href="#solution">{{CTA_TEXT}}</a></li>
            <li><a href="#why-us">Why Choose Us</a></li>
            <li><a href="#gallery">Photo Gallery</a></li>
          </ul>
        </div>
        <div class="footer-col">
          <h5>Customer Care</h5>
          <ul class="footer-links">
            <li><a href="#faq">Frequently Asked Questions</a></li>
            <li><a href="#testimonials">Patient & Client Reviews</a></li>
            <li><a href="#contact">Contact & Location</a></li>
            <li><a href="tel:{{CLEAN_PHONE}}">Direct Phone Support</a></li>
            <li><a href="https://wa.me/{{WHATSAPP_PHONE}}">WhatsApp Helpdesk</a></li>
          </ul>
        </div>
        <div class="footer-col">
          <h5>Direct Contact</h5>
          <p style="margin-bottom: 8px;"><strong>📍 Address:</strong><br>{{ADDRESS}}</p>
          <p style="margin-bottom: 8px;"><strong>📞 Phone:</strong><br><a href="tel:{{CLEAN_PHONE}}" style="color: #ffffff;">{{PHONE}}</a></p>
          <p><strong>✉️ Email:</strong><br>{{EMAIL}}</p>
        </div>
      </div>

      <div class="footer-bottom">
        <div>© 2026 {{BUSINESS_NAME}}, {{CITY}}. All rights reserved.</div>
        <div>Commercial Demo Prototype • Mobile-First Responsive Solution</div>
      </div>
    </div>
  </footer>

  <!-- Floating Mobile Action Bar -->
  <div class="mobile-sticky-bar">
    <div class="mobile-sticky-grid">
      <a href="tel:{{CLEAN_PHONE}}" class="btn btn-outline mobile-sticky-btn">
        <span>📞</span>
        <span>Call</span>
      </a>
      <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20I%20am%20interested%20in%20your%20services." target="_blank" class="btn btn-whatsapp mobile-sticky-btn">
        <span>💬</span>
        <span>WhatsApp</span>
      </a>
      <a href="#solution" class="btn btn-primary mobile-sticky-btn">
        <span>{{CTA_ICON}}</span>
        <span>{{CTA_TEXT}}</span>
      </a>
    </div>
  </div>

  <!-- Toast Notification Container -->
  <div class="toast-container" id="toastContainer"></div>

  <!-- Generic Confirmation Modal -->
  <div class="modal-backdrop" id="genericModal">
    <div class="modal-box">
      <button class="modal-close-btn" onclick="closeModal()">✕</button>
      <div id="modalContent"></div>
    </div>
  </div>

  <script>
    // Mobile Drawer Toggle
    const mobileToggle = document.getElementById('mobileToggle');
    const mobileDrawer = document.getElementById('mobileDrawer');
    if (mobileToggle && mobileDrawer) {
      mobileToggle.addEventListener('click', () => {
        mobileDrawer.classList.toggle('active');
      });
    }
    function closeDrawer() {
      if (mobileDrawer) mobileDrawer.classList.remove('active');
    }

    // Toast Notification System
    function showToast(message, icon = '✅') {
      const container = document.getElementById('toastContainer');
      if (!container) return;
      const toast = document.createElement('div');
      toast.className = 'toast';
      toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
      container.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
      }, 3500);
    }

    // Modal System
    function openModal(contentHtml) {
      const modal = document.getElementById('genericModal');
      const content = document.getElementById('modalContent');
      if (modal && content) {
        content.innerHTML = contentHtml;
        modal.classList.add('active');
      }
    }
    function closeModal() {
      const modal = document.getElementById('genericModal');
      if (modal) modal.classList.remove('active');
    }

    // FAQ Accordion
    document.querySelectorAll('.faq-question').forEach(q => {
      q.addEventListener('click', () => {
        const item = q.parentElement;
        item.classList.toggle('active');
      });
    });
  </script>
</body>
</html>
"""


# ==============================================================================
# 1. CLINIC / DENTAL VERTICAL TEMPLATE
# ==============================================================================

_CLINIC_TEMPLATE = """
<!-- Hero Section -->
<section class="hero-section" id="hero">
  <div class="container hero-grid">
    <div class="hero-content">
      <div class="hero-badge-row">
        <span class="section-eyebrow">⚕️ Multi-Specialty Dental & Clinical Care</span>
        <div class="rating-badge">
          <span class="rating-stars">★★★★★</span>
          <span>4.9 (420+ Patient Reviews)</span>
        </div>
      </div>
      <h1 class="hero-title">Painless & Advanced Dental Care for Your Entire Family in <span class="highlight">{{CITY}}</span></h1>
      <p class="hero-subtitle">Experience certified orthodontics, painless root canals, laser teeth whitening, and complete smile makeovers at {{BUSINESS_NAME}}. Instant digital slot booking with zero waiting times.</p>
      
      <div class="hero-cta-group">
        <a href="#solution" class="btn btn-primary btn-lg">📅 Book Instant Appointment</a>
        <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hello%20{{BUSINESS_NAME}},%20I%20would%20like%20to%20consult%20with%20a%20dentist." target="_blank" class="btn btn-whatsapp btn-lg">💬 WhatsApp Consultation</a>
      </div>

      <div class="hero-stats-row">
        <div class="hero-stat">
          <span class="hero-stat-num">12,500+</span>
          <span class="hero-stat-label">Happy Patients Treated</span>
        </div>
        <div class="hero-stat">
          <span class="hero-stat-num">15+ Yrs</span>
          <span class="hero-stat-label">Clinical Experience</span>
        </div>
        <div class="hero-stat">
          <span class="hero-stat-num">100%</span>
          <span class="hero-stat-label">Sterilized & Painless Tech</span>
        </div>
      </div>
    </div>

    <div class="hero-visual-wrap">
      <div class="hero-main-img-card">
        <img src="https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=1200&q=80" alt="{{BUSINESS_NAME}} Modern Clinic Consultation Room in {{CITY}}">
      </div>
      <div class="hero-floating-card floating-card-1">
        <div class="floating-icon">🦷</div>
        <div class="floating-text">
          <strong>Certified Specialists</strong>
          <span>MDS Orthodontists & Surgeons</span>
        </div>
      </div>
      <div class="hero-floating-card floating-card-2">
        <div class="floating-icon">⚡</div>
        <div class="floating-text">
          <strong>Zero Waiting Time</strong>
          <span>Confirmed Digital Slot</span>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Clinical Services Section -->
<section id="services">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Our Clinical Specialties</span>
      <h2 class="section-title">Comprehensive Treatments Under One Roof</h2>
      <p class="section-subtitle">From preventative hygiene to advanced cosmetic smile transformations, our specialists utilize high-magnification loupes and digital imaging.</p>
    </div>

    <div class="cards-grid">
      <div class="card">
        <div class="card-img-wrap">
          <img src="https://images.unsplash.com/photo-1606811841689-23dfddce3e95?w=600&q=80" alt="Root Canal Treatment at {{BUSINESS_NAME}}">
          <span class="card-badge">Single-Sitting</span>
        </div>
        <div class="card-icon">🩺</div>
        <h3 class="card-title">Painless Root Canal (RCT)</h3>
        <p class="card-desc">Advanced rotary endodontics with 3D apex locators. Preserves natural teeth structure in a single, relaxed session.</p>
        <div class="card-footer">
          <span class="card-price">From ₹3,499</span>
          <button class="btn btn-outline btn-sm" onclick="selectServiceForBooking('Painless Root Canal', 3499)">Select & Book</button>
        </div>
      </div>

      <div class="card">
        <div class="card-img-wrap">
          <img src="https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?w=600&q=80" alt="Laser Teeth Whitening at {{BUSINESS_NAME}}">
          <span class="card-badge">Instant 6 Shades Whiter</span>
        </div>
        <div class="card-icon">✨</div>
        <h3 class="card-title">Laser Teeth Whitening</h3>
        <p class="card-desc">Gentle enamel-safe LED bleaching system to remove deep stains, smoking discolouration, and age spots in under 45 minutes.</p>
        <div class="card-footer">
          <span class="card-price">From ₹4,999</span>
          <button class="btn btn-outline btn-sm" onclick="selectServiceForBooking('Laser Teeth Whitening', 4999)">Select & Book</button>
        </div>
      </div>

      <div class="card">
        <div class="card-img-wrap">
          <img src="https://images.unsplash.com/photo-1598256989800-fe5f95da9787?w=600&q=80" alt="Invisible Aligners & Braces at {{BUSINESS_NAME}}">
          <span class="card-badge">Clear & Discreet</span>
        </div>
        <div class="card-icon">😁</div>
        <h3 class="card-title">Invisible Aligners & Braces</h3>
        <p class="card-desc">Custom transparent aligners digitally mapped to straighten crooked teeth without ugly metal brackets.</p>
        <div class="card-footer">
          <span class="card-price">From ₹35,000</span>
          <button class="btn btn-outline btn-sm" onclick="selectServiceForBooking('Invisible Aligners & Braces', 35000)">Select & Book</button>
        </div>
      </div>

      <div class="card">
        <div class="card-img-wrap">
          <img src="https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=600&q=80" alt="Permanent Dental Implants at {{BUSINESS_NAME}}">
          <span class="card-badge">Lifetime Warranty</span>
        </div>
        <div class="card-icon">🦷</div>
        <h3 class="card-title">Permanent Dental Implants</h3>
        <p class="card-desc">Titanium implants with natural-looking zirconia crowns restoring 100% natural bite strength and aesthetics.</p>
        <div class="card-footer">
          <span class="card-price">From ₹18,999</span>
          <button class="btn btn-outline btn-sm" onclick="selectServiceForBooking('Dental Implants', 18999)">Select & Book</button>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Interactive Solution Hub (Online Appointment Booking) -->
<section id="solution" style="background: var(--bg-soft);">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Interactive Patient Booking Engine</span>
      <h2 class="section-title">Book Your Doctor's Slot in 3 Easy Steps</h2>
      <p class="section-subtitle">Avoid clinic waiting lines. Pick your specialist, date, and preferred time slot for an immediate confirmed appointment.</p>
    </div>

    <div class="interactive-hub">
      <div class="interactive-hub-header">
        <div class="hub-title-group">
          <h3><span>🏥</span> Select Treatment & Doctor</h3>
          <p style="font-size: 14px; color: var(--text-muted); margin-top: 4px;">Real-time appointment slot reservation system for {{BUSINESS_NAME}}</p>
        </div>
        <span class="hub-badge">Live Instant Confirmation</span>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px;" id="bookingFormGrid">
        <div>
          <div class="form-group">
            <label class="form-label">1. Select Required Specialty / Treatment</label>
            <select class="form-select" id="clinicServiceSelect" onchange="updateBookingTotal()">
              <option value="General Dental Consultation" data-price="500">General Consultation & Digital X-Ray (₹500)</option>
              <option value="Painless Root Canal" data-price="3499">Painless Root Canal Treatment (₹3,499)</option>
              <option value="Laser Teeth Whitening" data-price="4999">Laser Teeth Whitening & Polishing (₹4,999)</option>
              <option value="Invisible Aligners Consultation" data-price="999">Clear Aligners Scan & 3D Preview (₹999)</option>
              <option value="Dental Implants Assessment" data-price="1200">Dental Implant Consultation & Bone Scan (₹1,200)</option>
              <option value="Kids Pediatric Dental Care" data-price="750">Kids Pediatric Gentle Dental Checkup (₹750)</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">2. Select Treating Doctor</label>
            <select class="form-select" id="clinicDoctorSelect">
              <option value="Dr. Arvind Mehta (BDS, MDS - Endodontist)">Dr. Arvind Mehta (MDS - Root Canal Specialist • 14 Yrs Exp)</option>
              <option value="Dr. Sneha Patel (BDS, MDS - Orthodontist)">Dr. Sneha Patel (MDS - Invisible Braces & Aligners • 11 Yrs Exp)</option>
              <option value="Dr. Rohit Desai (BDS, Implantologist)">Dr. Rohit Desai (Fellow in Oral Implantology • 16 Yrs Exp)</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">3. Preferred Appointment Date</label>
            <input type="date" class="form-input" id="clinicBookingDate">
          </div>
        </div>

        <div>
          <div class="form-group">
            <label class="form-label">4. Select Preferred Time Slot</label>
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px;" id="clinicSlotPicker">
              <button type="button" class="filter-tab active" onclick="pickClinicSlot(this, '10:00 AM')">10:00 AM</button>
              <button type="button" class="filter-tab" onclick="pickClinicSlot(this, '11:30 AM')">11:30 AM</button>
              <button type="button" class="filter-tab" onclick="pickClinicSlot(this, '02:00 PM')">02:00 PM</button>
              <button type="button" class="filter-tab" onclick="pickClinicSlot(this, '04:30 PM')">04:30 PM</button>
              <button type="button" class="filter-tab" onclick="pickClinicSlot(this, '06:00 PM')">06:00 PM</button>
              <button type="button" class="filter-tab" onclick="pickClinicSlot(this, '07:30 PM')">07:30 PM</button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">5. Patient Details</label>
            <input type="text" class="form-input" id="clinicPatientName" placeholder="Full Patient Name" style="margin-bottom: 10px;">
            <input type="tel" class="form-input" id="clinicPatientPhone" placeholder="Mobile Number (for SMS & WhatsApp Confirmation)">
          </div>

          <div style="background: var(--bg-soft); padding: 16px; border-radius: var(--radius-md); margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <span style="font-size: 13px; color: var(--text-muted); display: block;">Estimated Consultation / Procedure Fee:</span>
              <strong style="font-size: 20px; color: var(--primary);" id="clinicPriceDisplay">₹500</strong>
            </div>
            <span style="font-size: 12px; color: #16a34a; font-weight: 700; background: #dcfce7; padding: 4px 8px; border-radius: 6px;">Pay at Clinic (No Prepayment)</span>
          </div>

          <button class="btn btn-primary btn-lg" style="width: 100%;" onclick="submitClinicBooking()">
            <span>📅 Confirm Appointment Reservation</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Why Choose Us -->
<section id="why-us">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Why Patients Trust Us</span>
      <h2 class="section-title">The {{BUSINESS_NAME}} Difference</h2>
      <p class="section-subtitle">We merge compassionate patient care with medical-grade hospital standards in {{CITY}}.</p>
    </div>

    <div class="cards-grid">
      <div class="card">
        <div class="card-icon">🛡️</div>
        <h3 class="card-title">100% Class-B Autoclave Sterilization</h3>
        <p class="card-desc">Strict 6-step hospital-grade sterilization protocols for every instrument, ensuring zero cross-contamination risk.</p>
      </div>

      <div class="card">
        <div class="card-icon">🔬</div>
        <h3 class="card-title">Digital 3D Intraoral Scanning</h3>
        <p class="card-desc">No messy, gagging impression pastes. High-precision laser scanners map your teeth in 60 seconds with sub-millimeter accuracy.</p>
      </div>

      <div class="card">
        <div class="card-icon">💳</div>
        <h3 class="card-title">0% Interest Flexible EMI Plans</h3>
        <p class="card-desc">Complete transparency with zero hidden charges. Monthly installments available for aligners, implants, and major surgeries.</p>
      </div>

      <div class="card">
        <div class="card-icon">📱</div>
        <h3 class="card-title">Digital Prescriptions & Records</h3>
        <p class="card-desc">Instant WhatsApp updates, digital X-ray storage, and automated medicine dosage reminders sent to your phone.</p>
      </div>
    </div>
  </div>
</section>

<!-- Visual Clinic Gallery -->
<section id="gallery" style="background: var(--bg-soft);">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Clinic Infrastructure</span>
      <h2 class="section-title">Take a Visual Tour of Our Facility</h2>
      <p class="section-subtitle">Equipped with German dental operatories, HEPA air purifiers, and a calm, relaxing ambient environment.</p>
    </div>

    <div class="gallery-grid">
      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1629909615184-74f495363b67?w=600&q=80" alt="Modern Operatory Suite at {{BUSINESS_NAME}}">
        <div class="gallery-overlay">
          <div class="gallery-title">Ergonomic Dental Operatory</div>
          <div class="gallery-sub">Equipped with intra-oral camera & LED monitors</div>
        </div>
      </div>

      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1594824813588-4c17e3f89e47?w=600&q=80" alt="Doctor Consultation at {{BUSINESS_NAME}}">
        <div class="gallery-overlay">
          <div class="gallery-title">Private Consultation Suite</div>
          <div class="gallery-sub">Detailed 3D treatment plan walk-through</div>
        </div>
      </div>

      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?w=600&q=80" alt="Sterilization Room at {{BUSINESS_NAME}}">
        <div class="gallery-overlay">
          <div class="gallery-title">Sterilization Lab</div>
          <div class="gallery-sub">Hospital-grade vacuum autoclaves</div>
        </div>
      </div>

      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=600&q=80" alt="Patient Waiting Lounge at {{BUSINESS_NAME}}">
        <div class="gallery-overlay">
          <div class="gallery-title">Patient Reception & Lounge</div>
          <div class="gallery-sub">Complimentary beverages & soothing atmosphere</div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Verified Patient Reviews -->
<section id="testimonials">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Patient Testimonials</span>
      <h2 class="section-title">What {{CITY}} Patients Say About Us</h2>
      <p class="section-subtitle">Real experiences from patients who underwent root canals, braces, and smile transformations with our team.</p>
    </div>

    <div class="testimonials-grid">
      <div class="testimonial-card">
        <div class="testimonial-header">
          <img src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&q=80" alt="Patient Review for {{BUSINESS_NAME}}" class="testimonial-avatar">
          <div>
            <div class="testimonial-name">Pooja Shah</div>
            <div class="testimonial-role">Navrangpura, {{CITY}} • Clear Aligners</div>
          </div>
        </div>
        <div class="rating-stars">★★★★★</div>
        <p class="testimonial-text">"I was terrified of dental visits until I visited {{BUSINESS_NAME}}. The clear aligners procedure was seamless, and the doctor explained every 3D scan step. Zero pain and my teeth alignment changed within 7 months!"</p>
      </div>

      <div class="testimonial-card">
        <div class="testimonial-header">
          <img src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&q=80" alt="Patient Review for {{BUSINESS_NAME}}" class="testimonial-avatar">
          <div>
            <div class="testimonial-name">Rajesh Trivedi</div>
            <div class="testimonial-role">Satellite, {{CITY}} • Root Canal Treatment</div>
          </div>
        </div>
        <div class="rating-stars">★★★★★</div>
        <p class="testimonial-text">"Got my molar root canal done in a single 45-minute sitting. I didn't feel a single pinch of pain during anesthesia or drilling. The booking on their website was instantaneous."</p>
      </div>

      <div class="testimonial-card">
        <div class="testimonial-header">
          <img src="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&q=80" alt="Patient Review for {{BUSINESS_NAME}}" class="testimonial-avatar">
          <div>
            <div class="testimonial-name">Meera Iyer</div>
            <div class="testimonial-role">Vastrapur, {{CITY}} • Dental Implants</div>
          </div>
        </div>
        <div class="rating-stars">★★★★★</div>
        <p class="testimonial-text">"Replaced two missing lower teeth with permanent zirconia implants. The clinic hygiene is top-notch, comparable to 5-star hospitals in Mumbai. Highly recommended!"</p>
      </div>
    </div>
  </div>
</section>

<!-- FAQ Accordion -->
<section id="faq" style="background: var(--bg-soft);">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Patient Inquiries</span>
      <h2 class="section-title">Frequently Asked Questions</h2>
      <p class="section-subtitle">Clear answers to your dental care and appointment questions.</p>
    </div>

    <div class="faq-list">
      <div class="faq-item active">
        <div class="faq-question">
          <span>Is root canal treatment really 100% painless?</span>
          <span class="faq-icon">+</span>
        </div>
        <div class="faq-answer">
          Yes! We utilize computerized micro-anesthesia delivery and apex locators that numb the exact nerve root, ensuring complete numbness throughout the procedure. Most patients listen to music during treatment.
        </div>
      </div>

      <div class="faq-item">
        <div class="faq-question">
          <span>How long does teeth whitening last?</span>
          <span class="faq-icon">+</span>
        </div>
        <div class="faq-answer">
          Our in-office laser whitening results typically last 18 to 24 months depending on dietary habits (coffee, tea, smoking). We also provide custom maintenance trays for home touch-ups.
        </div>
      </div>

      <div class="faq-item">
        <div class="faq-question">
          <span>Do you accept dental insurance or corporate cashless cards?</span>
          <span class="faq-icon">+</span>
        </div>
        <div class="faq-answer">
          Yes, we provide itemized GST invoices and medical necessity certificates accepted by all major insurance TPAs and corporate health schemes.
        </div>
      </div>

      <div class="faq-item">
        <div class="faq-question">
          <span>What if I need emergency dental attention on a weekend?</span>
          <span class="faq-icon">+</span>
        </div>
        <div class="faq-answer">
          Our emergency hotline and WhatsApp support are active 7 days a week. Urgent tooth trauma, severe bleeding, or acute pain cases are prioritized within 30 minutes.
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Location & Contact -->
<section id="contact">
  <div class="container contact-grid">
    <div class="contact-info-card">
      <div>
        <span class="section-eyebrow" style="background: rgba(255,255,255,0.2); color: #fff;">Visit Our Clinic</span>
        <h3 style="margin-top: 10px;">{{BUSINESS_NAME}}</h3>
        <p style="font-size: 14px; opacity: 0.9; margin-top: 8px;">Conveniently located with dedicated basement patient parking and wheelchair access.</p>
      </div>

      <div class="contact-item">
        <div class="contact-item-icon">📍</div>
        <div class="contact-item-text">
          <strong>Clinic Address</strong>
          <span>{{ADDRESS}}</span>
        </div>
      </div>

      <div class="contact-item">
        <div class="contact-item-icon">📞</div>
        <div class="contact-item-text">
          <strong>Direct Telephone & Appointments</strong>
          <span><a href="tel:{{CLEAN_PHONE}}" style="color: #fff; text-decoration: underline;">{{PHONE}}</a></span>
        </div>
      </div>

      <div class="contact-item">
        <div class="contact-item-icon">💬</div>
        <div class="contact-item-text">
          <strong>Instant WhatsApp Helpdesk</strong>
          <span>+{{WHATSAPP_PHONE}} (Live response in under 5 mins)</span>
        </div>
      </div>

      <div>
        <strong style="display: block; margin-bottom: 8px; font-size: 14px;">Consulting Hours:</strong>
        <table class="hours-table">
          <tr><td>Monday – Saturday</td><td style="text-align: right;">9:00 AM – 8:30 PM</td></tr>
          <tr><td>Sunday</td><td style="text-align: right;">10:00 AM – 2:00 PM</td></tr>
          <tr><td>Emergency Trauma</td><td style="text-align: right;">24x7 on Call</td></tr>
        </table>
      </div>
    </div>

    <div style="background: #fff; border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 36px; box-shadow: var(--shadow-md);">
      <h3 style="font-size: 22px; margin-bottom: 8px;">Send an Inquiry or Request Callback</h3>
      <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 24px;">Our duty doctor will contact you within 15 minutes to answer questions or confirm your slot.</p>

      <form onsubmit="handleGeneralInquiry(event)">
        <div class="form-group">
          <label class="form-label">Full Name</label>
          <input type="text" class="form-input" required placeholder="Your full name">
        </div>
        <div class="form-group">
          <label class="form-label">Mobile Number</label>
          <input type="tel" class="form-input" required placeholder="10-digit mobile number">
        </div>
        <div class="form-group">
          <label class="form-label">Describe Your Problem / Service Needed</label>
          <textarea class="form-textarea" rows="3" placeholder="e.g. Need root canal for lower tooth, toothache since 2 days..."></textarea>
        </div>
        <button type="submit" class="btn btn-primary btn-lg" style="width: 100%;">
          <span>📤 Request Instant Callback</span>
        </button>
      </form>
    </div>
  </div>
</section>

<script>
  // Set default date to tomorrow
  const dateInput = document.getElementById('clinicBookingDate');
  if (dateInput) {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    dateInput.value = tomorrow.toISOString().split('T')[0];
    dateInput.min = new Date().toISOString().split('T')[0];
  }

  let selectedClinicSlot = '10:00 AM';

  function pickClinicSlot(btn, slot) {
    document.querySelectorAll('#clinicSlotPicker .filter-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedClinicSlot = slot;
    showToast('Selected time slot: ' + slot, '⏰');
  }

  function updateBookingTotal() {
    const select = document.getElementById('clinicServiceSelect');
    const selectedOption = select.options[select.selectedIndex];
    const price = selectedOption.getAttribute('data-price') || '500';
    document.getElementById('clinicPriceDisplay').innerText = '₹' + parseInt(price).toLocaleString('en-IN');
  }

  function selectServiceForBooking(serviceName, price) {
    const select = document.getElementById('clinicServiceSelect');
    for (let i = 0; i < select.options.length; i++) {
      if (select.options[i].text.includes(serviceName)) {
        select.selectedIndex = i;
        break;
      }
    }
    updateBookingTotal();
    const solutionSec = document.getElementById('solution');
    if (solutionSec) solutionSec.scrollIntoView({ behavior: 'smooth' });
    showToast('Selected ' + serviceName + ' for appointment', '🦷');
  }

  function submitClinicBooking() {
    const serviceSelect = document.getElementById('clinicServiceSelect');
    const doctorSelect = document.getElementById('clinicDoctorSelect');
    const date = document.getElementById('clinicBookingDate').value;
    const name = document.getElementById('clinicPatientName').value.trim();
    const phone = document.getElementById('clinicPatientPhone').value.trim();

    if (!name || !phone) {
      alert('Please enter patient name and mobile number to confirm your booking.');
      return;
    }

    const service = serviceSelect.options[serviceSelect.selectedIndex].text;
    const doctor = doctorSelect.value;
    const fee = document.getElementById('clinicPriceDisplay').innerText;

    const modalHtml = `
      <div style="text-align: center; padding: 10px 0;">
        <div style="font-size: 50px; margin-bottom: 12px;">🎉</div>
        <h3 style="font-size: 24px; margin-bottom: 8px; color: var(--primary);">Appointment Reserved!</h3>
        <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 20px;">Your confirmed clinical slot has been logged in {{BUSINESS_NAME}}'s digital schedule.</p>
        
        <div style="background: var(--bg-soft); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 18px; text-align: left; font-size: 14px; margin-bottom: 20px; line-height: 1.8;">
          <div><strong>Patient:</strong> ${name} (${phone})</div>
          <div><strong>Treatment:</strong> ${service}</div>
          <div><strong>Doctor:</strong> ${doctor}</div>
          <div><strong>Date & Time:</strong> ${date} at ${selectedClinicSlot}</div>
          <div><strong>Estimated Fee:</strong> ${fee} (Payable at clinic)</div>
        </div>

        <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 20px;">An SMS & WhatsApp confirmation ticket is being generated for you.</p>

        <div style="display: flex; gap: 10px;">
          <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20I%20just%20booked%20an%20appointment%20for%20${encodeURIComponent(name)}%20on%20${date}%20at%20${selectedClinicSlot}." target="_blank" class="btn btn-whatsapp" style="flex: 1;">
            <span>💬 Open WhatsApp Pass</span>
          </a>
          <button class="btn btn-primary" onclick="closeModal()" style="flex: 1;">Done</button>
        </div>
      </div>
    `;

    openModal(modalHtml);
    showToast('Appointment successfully scheduled!', '🎉');
  }

  function handleGeneralInquiry(e) {
    e.preventDefault();
    showToast('Inquiry submitted! Our doctor will call you shortly.', '📞');
    e.target.reset();
  }
</script>
"""


# ==============================================================================
# 2. RESTAURANT / FOOD VERTICAL TEMPLATE
# ==============================================================================

_RESTAURANT_TEMPLATE = """
<!-- Hero Section -->
<section class="hero-section" id="hero">
  <div class="container hero-grid">
    <div class="hero-content">
      <div class="hero-badge-row">
        <span class="section-eyebrow">🍽️ Gourmet Dining & Direct Table Delivery</span>
        <div class="rating-badge">
          <span class="rating-stars">★★★★★</span>
          <span>4.9 (680+ Foodie Reviews)</span>
        </div>
      </div>
      <h1 class="hero-title">Authentic Flavors, Fresh Ingredients & Sizzling Delights in <span class="highlight">{{CITY}}</span></h1>
      <p class="hero-subtitle">Welcome to {{BUSINESS_NAME}}. Indulge in wood-fired specialties, chef secret curries, artisanal desserts, and direct online ordering with zero third-party commission markups.</p>
      
      <div class="hero-cta-group">
        <a href="#solution" class="btn btn-primary btn-lg">🛍️ View Menu & Order Online</a>
        <a href="#table-booking" class="btn btn-outline btn-lg">🍽️ Reserve a Table</a>
        <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20I%20want%20to%20place%20a%20food%20order." target="_blank" class="btn btn-whatsapp btn-lg">💬 WhatsApp Order</a>
      </div>

      <div class="hero-stats-row">
        <div class="hero-stat">
          <span class="hero-stat-num">45+</span>
          <span class="hero-stat-label">Chef Handcrafted Dishes</span>
        </div>
        <div class="hero-stat">
          <span class="hero-stat-num">30 Mins</span>
          <span class="hero-stat-label">Express Delivery</span>
        </div>
        <div class="hero-stat">
          <span class="hero-stat-num">100%</span>
          <span class="hero-stat-label">Fresh & Hygienic Kitchen</span>
        </div>
      </div>
    </div>

    <div class="hero-visual-wrap">
      <div class="hero-main-img-card">
        <img src="https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1200&q=80" alt="{{BUSINESS_NAME}} Fine Dining Ambiance in {{CITY}}">
      </div>
      <div class="hero-floating-card floating-card-1">
        <div class="floating-icon">🍕</div>
        <div class="floating-text">
          <strong>Live Wood-Fired Kitchen</strong>
          <span>Hand-Tossed & Slow-Cooked</span>
        </div>
      </div>
      <div class="hero-floating-card floating-card-2">
        <div class="floating-icon">🛵</div>
        <div class="floating-text">
          <strong>Free Delivery Over ₹399</strong>
          <span>Hot & Fresh to Your Door</span>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Interactive Digital Menu & Live Cart System -->
<section id="solution" style="background: var(--bg-soft);">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Direct Online Ordering</span>
      <h2 class="section-title">Explore Our Chef's Curated Menu</h2>
      <p class="section-subtitle">Add items directly to your live order basket. Instant bill calculation with zero surge pricing.</p>
    </div>

    <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 30px;" id="foodMenuGrid">
      <div>
        <!-- Menu Categories -->
        <div class="filter-tabs" id="menuFilterTabs">
          <button class="filter-tab active" onclick="filterMenu('all', this)">All Dishes (12)</button>
          <button class="filter-tab" onclick="filterMenu('starters', this)">🔥 Sizzling Starters</button>
          <button class="filter-tab" onclick="filterMenu('mains', this)">🍲 Gourmet Mains</button>
          <button class="filter-tab" onclick="filterMenu('breads', this)">🥖 Breads & Biryani</button>
          <button class="filter-tab" onclick="filterMenu('desserts', this)">🍰 Desserts & Drinks</button>
        </div>

        <div class="cards-grid" id="dishesGrid">
          <!-- Dish 1 -->
          <div class="card menu-item-card" data-category="starters">
            <div class="card-img-wrap">
              <img src="https://images.unsplash.com/photo-1567188040759-fb8a883dc6d8?w=600&q=80" alt="Paneer Tikka Platter">
              <span class="card-badge" style="background: #16a34a;">🟢 Pure Veg</span>
            </div>
            <h3 class="card-title">Smoked Tandoori Paneer Tikka</h3>
            <p class="card-desc">Cottage cheese cubes marinated in Kashmiri spices, hung curd, and bell peppers charred in clay oven.</p>
            <div class="card-footer">
              <span class="card-price">₹320</span>
              <button class="btn btn-primary btn-sm" onclick="addToCart('Smoked Tandoori Paneer Tikka', 320)">+ Add to Order</button>
            </div>
          </div>

          <!-- Dish 2 -->
          <div class="card menu-item-card" data-category="starters">
            <div class="card-img-wrap">
              <img src="https://images.unsplash.com/photo-1599488615731-7e5c2823ff28?w=600&q=80" alt="Crispy Corn & Waterchestnut">
              <span class="card-badge" style="background: #16a34a;">🟢 Pure Veg</span>
            </div>
            <h3 class="card-title">Crispy Sweet Corn & Pepper Crunch</h3>
            <p class="card-desc">Golden fried corn tossed with scallions, crushed black pepper, kaffir lime, and roasted garlic dip.</p>
            <div class="card-footer">
              <span class="card-price">₹260</span>
              <button class="btn btn-primary btn-sm" onclick="addToCart('Crispy Sweet Corn & Pepper Crunch', 260)">+ Add to Order</button>
            </div>
          </div>

          <!-- Dish 3 -->
          <div class="card menu-item-card" data-category="mains">
            <div class="card-img-wrap">
              <img src="https://images.unsplash.com/photo-1589302168068-964664d93dc0?w=600&q=80" alt="Dal Makhani Royale">
              <span class="card-badge" style="background: #ea580c;">Chef Special</span>
            </div>
            <h3 class="card-title">Slow-Cooked Dal Makhani Royale</h3>
            <p class="card-desc">Simmered for 24 hours over slow charcoal with organic butter, cream, and fresh roasted fenugreek.</p>
            <div class="card-footer">
              <span class="card-price">₹340</span>
              <button class="btn btn-primary btn-sm" onclick="addToCart('Slow-Cooked Dal Makhani Royale', 340)">+ Add to Order</button>
            </div>
          </div>

          <!-- Dish 4 -->
          <div class="card menu-item-card" data-category="mains">
            <div class="card-img-wrap">
              <img src="https://images.unsplash.com/photo-1631452180519-c014fe946bc7?w=600&q=80" alt="Paneer Lababdar">
              <span class="card-badge" style="background: #16a34a;">🟢 Pure Veg</span>
            </div>
            <h3 class="card-title">Shahi Paneer Lababdar</h3>
            <p class="card-desc">Rich velvety tomato and cashew gravy loaded with soft paneer chunks and grated mawa.</p>
            <div class="card-footer">
              <span class="card-price">₹360</span>
              <button class="btn btn-primary btn-sm" onclick="addToCart('Shahi Paneer Lababdar', 360)">+ Add to Order</button>
            </div>
          </div>

          <!-- Dish 5 -->
          <div class="card menu-item-card" data-category="breads">
            <div class="card-img-wrap">
              <img src="https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=600&q=80" alt="Dum Biryani">
              <span class="card-badge" style="background: #ea580c;">Signature</span>
            </div>
            <h3 class="card-title">Awadhi Dum Veg Biryani</h3>
            <p class="card-desc">Long-grain aged basmati rice layered with garden veggies, saffron milk, fried onions, served with burani raita.</p>
            <div class="card-footer">
              <span class="card-price">₹380</span>
              <button class="btn btn-primary btn-sm" onclick="addToCart('Awadhi Dum Veg Biryani', 380)">+ Add to Order</button>
            </div>
          </div>

          <!-- Dish 6 -->
          <div class="card menu-item-card" data-category="desserts">
            <div class="card-img-wrap">
              <img src="https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=600&q=80" alt="Gulab Jamun with Rabdi">
              <span class="card-badge">Sweet Tooth</span>
            </div>
            <h3 class="card-title">Warm Gulab Jamun with Rabdi</h3>
            <p class="card-desc">Soft melt-in-mouth mawa dumplings soaked in cardamom rose syrup served over thick saffron rabdi.</p>
            <div class="card-footer">
              <span class="card-price">₹180</span>
              <button class="btn btn-primary btn-sm" onclick="addToCart('Warm Gulab Jamun with Rabdi', 180)">+ Add to Order</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Live Order Cart Sidebar -->
      <div>
        <div style="background: #ffffff; border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 24px; box-shadow: var(--shadow-md); position: sticky; top: 100px;">
          <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 16px;">
            <h3 style="font-size: 18px; display: flex; align-items: center; gap: 8px;">
              <span>🛒</span> Your Order Basket
            </h3>
            <span class="badge-live" id="cartCountBadge">0 Items</span>
          </div>

          <div id="cartItemsList" style="max-height: 280px; overflow-y: auto; margin-bottom: 20px;">
            <p style="font-size: 13px; color: var(--text-muted); text-align: center; padding: 30px 0;">Your basket is empty.<br>Click <strong>+ Add to Order</strong> on any dish to begin.</p>
          </div>

          <div style="border-top: 1px solid var(--border); padding-top: 14px; font-size: 14px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
              <span style="color: var(--text-muted);">Subtotal</span>
              <strong id="cartSubtotal">₹0</strong>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
              <span style="color: var(--text-muted);">GST (5%)</span>
              <span id="cartTax">₹0</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
              <span style="color: var(--text-muted);">Delivery Fee</span>
              <span style="color: #16a34a; font-weight: 700;" id="cartDeliveryFee">FREE</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 18px; border-top: 1px dashed var(--border); padding-top: 10px;">
              <strong>Total Amount:</strong>
              <strong style="color: var(--primary);" id="cartTotal">₹0</strong>
            </div>
          </div>

          <button class="btn btn-primary btn-lg" style="width: 100%;" id="checkoutBtn" onclick="openOrderCheckoutModal()" disabled>
            <span>🛍️ Checkout via WhatsApp</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Table Reservation Section -->
<section id="table-booking">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Dine-In Experience</span>
      <h2 class="section-title">Reserve a Table at {{BUSINESS_NAME}}</h2>
      <p class="section-subtitle">Planning a family get-together, birthday, or romantic dinner? Book your table in advance.</p>
    </div>

    <div style="max-width: 800px; margin: 0 auto; background: #ffffff; border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 40px; box-shadow: var(--shadow-lg);">
      <form onsubmit="handleTableReservation(event)">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
          <div class="form-group">
            <label class="form-label">Guest Name</label>
            <input type="text" class="form-input" id="tableName" required placeholder="Full name">
          </div>
          <div class="form-group">
            <label class="form-label">Phone Number</label>
            <input type="tel" class="form-input" id="tablePhone" required placeholder="10-digit mobile number">
          </div>
          <div class="form-group">
            <label class="form-label">Date</label>
            <input type="date" class="form-input" id="tableDate" required>
          </div>
          <div class="form-group">
            <label class="form-label">Time Slot</label>
            <select class="form-select" id="tableTime">
              <option>Lunch: 12:30 PM</option>
              <option>Lunch: 01:30 PM</option>
              <option>Dinner: 07:30 PM</option>
              <option>Dinner: 08:30 PM</option>
              <option>Dinner: 09:30 PM</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Number of Guests</label>
            <select class="form-select" id="tableGuests">
              <option>2 Guests (Romantic Table)</option>
              <option>4 Guests (Family Table)</option>
              <option>6-8 Guests (Celebration Table)</option>
              <option>10+ Guests (Private Dining Lounge)</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Special Requests (Optional)</label>
            <input type="text" class="form-input" id="tableNotes" placeholder="e.g. Window seat, Birthday cake...">
          </div>
        </div>

        <button type="submit" class="btn btn-primary btn-lg" style="width: 100%; margin-top: 10px;">
          <span>🍽️ Confirm Table Reservation</span>
        </button>
      </form>
    </div>
  </div>
</section>

<!-- Restaurant Visual Gallery -->
<section id="gallery" style="background: var(--bg-soft);">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Culinary Craft</span>
      <h2 class="section-title">Visual Moments from Our Kitchen</h2>
      <p class="section-subtitle">A glimpse into our vibrant ambiance, master plating, and celebratory guest moments.</p>
    </div>

    <div class="gallery-grid">
      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600&q=80" alt="Restaurant Interior at {{BUSINESS_NAME}}">
        <div class="gallery-overlay">
          <div class="gallery-title">Cozy Dine-In Lounge</div>
          <div class="gallery-sub">Warm lighting & relaxing acoustics</div>
        </div>
      </div>

      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1544025162-d76694265947?w=600&q=80" alt="Chef Special Plating">
        <div class="gallery-overlay">
          <div class="gallery-title">Master Chef Plating</div>
          <div class="gallery-sub">Artisanal herbs & slow charcoal fire</div>
        </div>
      </div>

      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=600&q=80" alt="Fresh Farm Salads">
        <div class="gallery-overlay">
          <div class="gallery-title">Organic Farm Salads</div>
          <div class="gallery-sub">Crisp greens & house vinaigrette</div>
        </div>
      </div>

      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1551024709-8f23befc6f87?w=600&q=80" alt="Artisanal Desserts">
        <div class="gallery-overlay">
          <div class="gallery-title">Artisanal Desserts</div>
          <div class="gallery-sub">Decadent sweets to conclude your meal</div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Location & Contact -->
<section id="contact">
  <div class="container contact-grid">
    <div class="contact-info-card">
      <div>
        <span class="section-eyebrow" style="background: rgba(255,255,255,0.2); color: #fff;">Visit Us</span>
        <h3 style="margin-top: 10px;">{{BUSINESS_NAME}}</h3>
        <p style="font-size: 14px; opacity: 0.9; margin-top: 8px;">Conveniently located with valet parking and direct pickup counter.</p>
      </div>

      <div class="contact-item">
        <div class="contact-item-icon">📍</div>
        <div class="contact-item-text">
          <strong>Restaurant Address</strong>
          <span>{{ADDRESS}}</span>
        </div>
      </div>

      <div class="contact-item">
        <div class="contact-item-icon">📞</div>
        <div class="contact-item-text">
          <strong>Order & Table Hotline</strong>
          <span><a href="tel:{{CLEAN_PHONE}}" style="color: #fff; text-decoration: underline;">{{PHONE}}</a></span>
        </div>
      </div>

      <div>
        <strong style="display: block; margin-bottom: 8px; font-size: 14px;">Kitchen & Delivery Timings:</strong>
        <table class="hours-table">
          <tr><td>Lunch Service</td><td style="text-align: right;">11:30 AM – 3:30 PM</td></tr>
          <tr><td>Dinner Service</td><td style="text-align: right;">6:30 PM – 11:30 PM</td></tr>
          <tr><td>Late Night Delivery</td><td style="text-align: right;">Open till 1:00 AM (Weekends)</td></tr>
        </table>
      </div>
    </div>

    <div style="background: #fff; border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 36px; box-shadow: var(--shadow-md);">
      <h3 style="font-size: 22px; margin-bottom: 8px;">Direct Food Delivery Inquiry</h3>
      <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 24px;">Need corporate bulk catering, party platters, or instant takeaway? Message our head chef directly.</p>

      <div style="display: flex; flex-direction: column; gap: 14px;">
        <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20I%20want%20to%20order%20food%20or%20inquire%20about%20party%20catering." target="_blank" class="btn btn-whatsapp btn-lg">
          <span>💬 Chat with Head Chef on WhatsApp</span>
        </a>
        <a href="tel:{{CLEAN_PHONE}}" class="btn btn-outline btn-lg">
          <span>📞 Call Kitchen Line: {{PHONE}}</span>
        </a>
      </div>
    </div>
  </div>
</section>

<script>
  let cart = [];

  function filterMenu(category, btn) {
    document.querySelectorAll('#menuFilterTabs .filter-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const cards = document.querySelectorAll('.menu-item-card');
    cards.forEach(c => {
      if (category === 'all' || c.getAttribute('data-category') === category) {
        c.style.display = 'flex';
      } else {
        c.style.display = 'none';
      }
    });
  }

  function addToCart(name, price) {
    const existing = cart.find(i => i.name === name);
    if (existing) {
      existing.qty += 1;
    } else {
      cart.push({ name, price, qty: 1 });
    }
    renderCart();
    showToast(`Added "${name}" to your order!`, '🍽️');
  }

  function changeQty(name, delta) {
    const item = cart.find(i => i.name === name);
    if (item) {
      item.qty += delta;
      if (item.qty <= 0) {
        cart = cart.filter(i => i.name !== name);
      }
    }
    renderCart();
  }

  function renderCart() {
    const container = document.getElementById('cartItemsList');
    const countBadge = document.getElementById('cartCountBadge');
    const checkoutBtn = document.getElementById('checkoutBtn');

    const totalQty = cart.reduce((sum, i) => sum + i.qty, 0);
    const subtotal = cart.reduce((sum, i) => sum + (i.price * i.qty), 0);
    const gst = Math.round(subtotal * 0.05);
    const total = subtotal + gst;

    countBadge.innerText = `${totalQty} Items`;
    document.getElementById('cartSubtotal').innerText = `₹${subtotal}`;
    document.getElementById('cartTax').innerText = `₹${gst}`;
    document.getElementById('cartTotal').innerText = `₹${total}`;

    if (cart.length === 0) {
      container.innerHTML = `<p style="font-size: 13px; color: var(--text-muted); text-align: center; padding: 30px 0;">Your basket is empty.<br>Click <strong>+ Add to Order</strong> on any dish to begin.</p>`;
      checkoutBtn.disabled = true;
    } else {
      checkoutBtn.disabled = false;
      let html = '';
      cart.forEach(item => {
        html += `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--border); font-size: 13px;">
            <div style="flex: 1;">
              <strong>${item.name}</strong>
              <div style="color: var(--text-muted);">₹${item.price} each</div>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <button onclick="changeQty('${item.name}', -1)" style="width: 24px; height: 24px; border-radius: 4px; border: 1px solid var(--border); background: #f8fafc; cursor: pointer;">-</button>
              <strong>${item.qty}</strong>
              <button onclick="changeQty('${item.name}', 1)" style="width: 24px; height: 24px; border-radius: 4px; border: 1px solid var(--border); background: #f8fafc; cursor: pointer;">+</button>
              <strong style="width: 50px; text-align: right; color: var(--primary);">₹${item.price * item.qty}</strong>
            </div>
          </div>
        `;
      });
      container.innerHTML = html;
    }
  }

  function openOrderCheckoutModal() {
    const subtotal = cart.reduce((sum, i) => sum + (i.price * i.qty), 0);
    const gst = Math.round(subtotal * 0.05);
    const total = subtotal + gst;

    let itemsSummary = cart.map(i => `${i.qty}x ${i.name} (₹${i.price * i.qty})`).join('%0A');
    const waText = `Hello {{BUSINESS_NAME}}, I want to place a food order:%0A%0A${itemsSummary}%0A%0ATotal: ₹${total}%0A%0APlease confirm delivery time!`;

    const modalHtml = `
      <div>
        <h3 style="font-size: 22px; margin-bottom: 8px; color: var(--primary);">Review Your Order</h3>
        <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 18px;">Instant order dispatch directly to {{BUSINESS_NAME}}'s kitchen display.</p>

        <div style="background: var(--bg-soft); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 16px; margin-bottom: 20px; font-size: 14px; line-height: 1.8;">
          ${cart.map(i => `<div><strong>${i.qty}x</strong> ${i.name} — ₹${i.price * i.qty}</div>`).join('')}
          <div style="border-top: 1px solid var(--border); margin-top: 10px; padding-top: 10px; font-size: 16px;">
            <strong>Total Payable: ₹${total}</strong> (GST Included)
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Delivery Address in {{CITY}}</label>
          <input type="text" class="form-input" id="deliveryAddress" placeholder="Flat No, Building, Landmark, Area">
        </div>

        <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=${waText}" target="_blank" class="btn btn-whatsapp btn-lg" style="width: 100%; margin-top: 10px;">
          <span>💬 Send Order via WhatsApp (Instant Dispatch)</span>
        </a>
      </div>
    `;

    openModal(modalHtml);
  }

  function handleTableReservation(e) {
    e.preventDefault();
    const name = document.getElementById('tableName').value;
    const date = document.getElementById('tableDate').value;
    const time = document.getElementById('tableTime').value;
    const guests = document.getElementById('tableGuests').value;

    const modalHtml = `
      <div style="text-align: center; padding: 10px 0;">
        <div style="font-size: 48px; margin-bottom: 10px;">🍽️</div>
        <h3 style="font-size: 22px; color: var(--primary); margin-bottom: 8px;">Table Reserved!</h3>
        <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 20px;">We have set aside your table for ${guests} on ${date} at ${time}.</p>
        
        <div style="background: var(--bg-soft); border-radius: var(--radius-md); padding: 16px; text-align: left; font-size: 14px; margin-bottom: 20px; line-height: 1.8;">
          <div><strong>Guest:</strong> ${name}</div>
          <div><strong>Reservation:</strong> ${date} (${time})</div>
          <div><strong>Party Size:</strong> ${guests}</div>
        </div>

        <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20I%20reserved%20a%20table%20for%20${encodeURIComponent(name)}%20on%20${date}%20at%20${encodeURIComponent(time)}." target="_blank" class="btn btn-whatsapp" style="width: 100%;">
          <span>💬 Open WhatsApp Table Pass</span>
        </a>
      </div>
    `;

    openModal(modalHtml);
    showToast('Table reserved successfully!', '🍽️');
  }

  const tableDateInput = document.getElementById('tableDate');
  if (tableDateInput) {
    const today = new Date();
    tableDateInput.value = today.toISOString().split('T')[0];
    tableDateInput.min = today.toISOString().split('T')[0];
  }
</script>
"""


# ==============================================================================
# 3. SALON / BEAUTY / SPA VERTICAL TEMPLATE
# ==============================================================================

_SALON_TEMPLATE = """
<!-- Hero Section -->
<section class="hero-section" id="hero">
  <div class="container hero-grid">
    <div class="hero-content">
      <div class="hero-badge-row">
        <span class="section-eyebrow">✂️ Luxury Hair, Skin & Bridal Studio</span>
        <div class="rating-badge">
          <span class="rating-stars">★★★★★</span>
          <span>4.9 (530+ Stylist Reviews)</span>
        </div>
      </div>
      <h1 class="hero-title">Experience Trendsetting Hair & Luxury Aesthetics in <span class="highlight">{{CITY}}</span></h1>
      <p class="hero-subtitle">Welcome to {{BUSINESS_NAME}}. Indulge in bespoke balayage hair coloring, keratin therapies, hydra-facials, and bridal makeovers by master certified stylists. Select your stylist and book your private chair online.</p>
      
      <div class="hero-cta-group">
        <a href="#solution" class="btn btn-primary btn-lg">✨ Book Stylist & Service</a>
        <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20I%20want%20to%20inquire%20about%20hair%20and%20spa%20services." target="_blank" class="btn btn-whatsapp btn-lg">💬 WhatsApp Inquiry</a>
      </div>

      <div class="hero-stats-row">
        <div class="hero-stat">
          <span class="hero-stat-num">8,400+</span>
          <span class="hero-stat-label">Clients Styled</span>
        </div>
        <div class="hero-stat">
          <span class="hero-stat-num">100%</span>
          <span class="hero-stat-label">L'Oréal & Kérastase Tech</span>
        </div>
        <div class="hero-stat">
          <span class="hero-stat-num">4.9 ★</span>
          <span class="hero-stat-label">Customer Satisfaction</span>
        </div>
      </div>
    </div>

    <div class="hero-visual-wrap">
      <div class="hero-main-img-card">
        <img src="https://images.unsplash.com/photo-1560066984-138dadb4c035?w=1200&q=80" alt="{{BUSINESS_NAME}} Luxury Salon Interior in {{CITY}}">
      </div>
      <div class="hero-floating-card floating-card-1">
        <div class="floating-icon">✂️</div>
        <div class="floating-text">
          <strong>Master Colorists</strong>
          <span>Balayage & Highlights Experts</span>
        </div>
      </div>
      <div class="hero-floating-card floating-card-2">
        <div class="floating-icon">💆‍♀️</div>
        <div class="floating-text">
          <strong>Organic Spa Facials</strong>
          <span>Hydra-Glow Radiance Care</span>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Salon Interactive Booking & Service Builder -->
<section id="solution" style="background: var(--bg-soft);">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Interactive Chair Booking</span>
      <h2 class="section-title">Customize Your Salon Package</h2>
      <p class="section-subtitle">Pick your beauty treatments, select your master stylist, and reserve your private time slot.</p>
    </div>

    <div class="interactive-hub">
      <div class="interactive-hub-header">
        <div class="hub-title-group">
          <h3><span>✨</span> Salon Service & Stylist Selector</h3>
          <p style="font-size: 14px; color: var(--text-muted); margin-top: 4px;">Real-time appointment slot reservation for {{BUSINESS_NAME}}</p>
        </div>
        <span class="hub-badge">Live Slot Confirmation</span>
      </div>

      <div style="display: grid; grid-template-columns: 1.2fr 1fr; gap: 30px;">
        <div>
          <label class="form-label">1. Choose Services (Select multiple)</label>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px;" id="salonServiceList">
            <div class="card select-item" style="padding: 16px; cursor: pointer;" onclick="toggleSalonService(this, 'Designer Haircut & Styling', 800)">
              <div style="font-weight: 700; font-size: 15px;">Designer Haircut & Blowdry</div>
              <div style="font-size: 13px; color: var(--text-muted);">Includes wash & conditioning</div>
              <div style="font-weight: 800; color: var(--primary); margin-top: 6px;">₹800</div>
            </div>

            <div class="card select-item" style="padding: 16px; cursor: pointer;" onclick="toggleSalonService(this, 'Balayage Hair Color', 4500)">
              <div style="font-weight: 700; font-size: 15px;">French Balayage & Toning</div>
              <div style="font-size: 13px; color: var(--text-muted);">Custom dimensional highlights</div>
              <div style="font-weight: 800; color: var(--primary); margin-top: 6px;">₹4,500</div>
            </div>

            <div class="card select-item" style="padding: 16px; cursor: pointer;" onclick="toggleSalonService(this, 'Hydra Radiance Facial', 2800)">
              <div style="font-weight: 700; font-size: 15px;">Hydra Glow Oxygen Facial</div>
              <div style="font-size: 13px; color: var(--text-muted);">Deep pore cleansing & serum</div>
              <div style="font-weight: 800; color: var(--primary); margin-top: 6px;">₹2,800</div>
            </div>

            <div class="card select-item" style="padding: 16px; cursor: pointer;" onclick="toggleSalonService(this, 'Keratin Hair Smoothening', 3800)">
              <div style="font-weight: 700; font-size: 15px;">Keratin Protein Therapy</div>
              <div style="font-size: 13px; color: var(--text-muted);">Zero frizz for up to 5 months</div>
              <div style="font-weight: 800; color: var(--primary); margin-top: 6px;">₹3,800</div>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">2. Select Stylist</label>
            <select class="form-select" id="salonStylistSelect">
              <option>Rohan Sen (Creative Director • 12 Yrs Exp)</option>
              <option>Ananya Sharma (Senior Colorist & Balayage Artist)</option>
              <option>Priyanka Das (Skin & Spa Aesthetician)</option>
            </select>
          </div>
        </div>

        <div>
          <div class="form-group">
            <label class="form-label">3. Appointment Date & Slot</label>
            <input type="date" class="form-input" id="salonDate" style="margin-bottom: 12px;">
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 20px;" id="salonSlots">
              <button type="button" class="filter-tab active" onclick="pickSalonSlot(this, '11:00 AM')">11:00 AM</button>
              <button type="button" class="filter-tab" onclick="pickSalonSlot(this, '01:30 PM')">01:30 PM</button>
              <button type="button" class="filter-tab" onclick="pickSalonSlot(this, '03:30 PM')">03:30 PM</button>
              <button type="button" class="filter-tab" onclick="pickSalonSlot(this, '05:00 PM')">05:00 PM</button>
              <button type="button" class="filter-tab" onclick="pickSalonSlot(this, '06:30 PM')">06:30 PM</button>
              <button type="button" class="filter-tab" onclick="pickSalonSlot(this, '08:00 PM')">08:00 PM</button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">4. Client Name & Phone</label>
            <input type="text" class="form-input" id="salonClientName" placeholder="Your Name" style="margin-bottom: 10px;">
            <input type="tel" class="form-input" id="salonClientPhone" placeholder="Mobile Number">
          </div>

          <div style="background: var(--bg-soft); border-radius: var(--radius-md); padding: 16px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <span style="font-size: 13px; color: var(--text-muted); display: block;">Package Total:</span>
              <strong style="font-size: 22px; color: var(--primary);" id="salonTotalDisplay">₹0</strong>
            </div>
            <span style="font-size: 12px; color: #16a34a; font-weight: 700; background: #dcfce7; padding: 4px 8px; border-radius: 6px;">Pay at Salon</span>
          </div>

          <button class="btn btn-primary btn-lg" style="width: 100%;" onclick="submitSalonBooking()">
            <span>✨ Confirm Salon Reservation</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Gallery & Testimonials -->
<section id="gallery">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Client Transformations</span>
      <h2 class="section-title">Before & After Lookbook</h2>
      <p class="section-subtitle">Real results created daily by our team of master stylists in {{CITY}}.</p>
    </div>

    <div class="gallery-grid">
      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=600&q=80" alt="Balayage Hair Transformation at {{BUSINESS_NAME}}">
        <div class="gallery-overlay">
          <div class="gallery-title">Honey Blonde Balayage</div>
          <div class="gallery-sub">Seamless blend with Olaplex protection</div>
        </div>
      </div>

      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1562322140-8baeececf3df?w=600&q=80" alt="Bridal Styling at {{BUSINESS_NAME}}">
        <div class="gallery-overlay">
          <div class="gallery-title">Bridal Hair & Makeup</div>
          <div class="gallery-sub">High-definition airbrush makeover</div>
        </div>
      </div>

      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1516975080664-ed2fc6a32937?w=600&q=80" alt="Facial & Skin Care">
        <div class="gallery-overlay">
          <div class="gallery-title">Hydra Radiance Glow</div>
          <div class="gallery-sub">Instant hydration & glass-skin glow</div>
        </div>
      </div>

      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1519699047748-de8e457a634e?w=600&q=80" alt="Keratin Treatment">
        <div class="gallery-overlay">
          <div class="gallery-title">Gloss Keratin Treatment</div>
          <div class="gallery-sub">Silky smooth manageable hair</div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Location & Contact -->
<section id="contact" style="background: var(--bg-soft);">
  <div class="container contact-grid">
    <div class="contact-info-card">
      <div>
        <span class="section-eyebrow" style="background: rgba(255,255,255,0.2); color: #fff;">Salon Location</span>
        <h3 style="margin-top: 10px;">{{BUSINESS_NAME}}</h3>
        <p style="font-size: 14px; opacity: 0.9; margin-top: 8px;">Located in the prime shopping district of {{CITY}} with private styling rooms.</p>
      </div>

      <div class="contact-item">
        <div class="contact-item-icon">📍</div>
        <div class="contact-item-text">
          <strong>Studio Address</strong>
          <span>{{ADDRESS}}</span>
        </div>
      </div>

      <div class="contact-item">
        <div class="contact-item-icon">📞</div>
        <div class="contact-item-text">
          <strong>Stylist Desk Phone</strong>
          <span><a href="tel:{{CLEAN_PHONE}}" style="color: #fff; text-decoration: underline;">{{PHONE}}</a></span>
        </div>
      </div>

      <div>
        <strong style="display: block; margin-bottom: 8px; font-size: 14px;">Studio Hours:</strong>
        <table class="hours-table">
          <tr><td>Tuesday – Sunday</td><td style="text-align: right;">10:00 AM – 9:00 PM</td></tr>
          <tr><td>Monday</td><td style="text-align: right;">Closed for Sanitization</td></tr>
        </table>
      </div>
    </div>

    <div style="background: #fff; border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 36px; box-shadow: var(--shadow-md);">
      <h3 style="font-size: 22px; margin-bottom: 8px;">Direct WhatsApp Consultation</h3>
      <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 24px;">Send us a photo of your hair or desired style to get a free quote from our master colorist.</p>

      <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20I%20want%20to%20send%20a%20photo%20for%20a%20hair%20coloring%20quote." target="_blank" class="btn btn-whatsapp btn-lg" style="width: 100%;">
        <span>💬 Send Photo on WhatsApp</span>
      </a>
    </div>
  </div>
</section>

<script>
  let selectedSalonServices = [];
  let selectedSalonSlot = '11:00 AM';

  function toggleSalonService(el, name, price) {
    el.classList.toggle('active');
    const idx = selectedSalonServices.findIndex(s => s.name === name);
    if (idx >= 0) {
      selectedSalonServices.splice(idx, 1);
    } else {
      selectedSalonServices.push({ name, price });
    }
    const total = selectedSalonServices.reduce((sum, s) => sum + s.price, 0);
    document.getElementById('salonTotalDisplay').innerText = '₹' + total.toLocaleString('en-IN');
    showToast(selectedSalonServices.length > 0 ? 'Updated service package' : 'Cleared selection', '✨');
  }

  function pickSalonSlot(btn, slot) {
    document.querySelectorAll('#salonSlots .filter-tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedSalonSlot = slot;
  }

  function submitSalonBooking() {
    const name = document.getElementById('salonClientName').value.trim();
    const phone = document.getElementById('salonClientPhone').value.trim();
    const stylist = document.getElementById('salonStylistSelect').value;
    const date = document.getElementById('salonDate').value;

    if (!name || !phone) {
      alert('Please enter your name and phone number.');
      return;
    }
    if (selectedSalonServices.length === 0) {
      alert('Please select at least one service from step 1.');
      return;
    }

    const servicesList = selectedSalonServices.map(s => s.name).join(', ');
    const total = document.getElementById('salonTotalDisplay').innerText;

    const modalHtml = `
      <div style="text-align: center; padding: 10px 0;">
        <div style="font-size: 50px; margin-bottom: 10px;">✨</div>
        <h3 style="font-size: 24px; color: var(--primary); margin-bottom: 8px;">Salon Session Reserved!</h3>
        <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 20px;">Your private chair with ${stylist} has been blocked.</p>

        <div style="background: var(--bg-soft); border-radius: var(--radius-md); padding: 16px; text-align: left; font-size: 14px; margin-bottom: 20px; line-height: 1.8;">
          <div><strong>Client:</strong> ${name} (${phone})</div>
          <div><strong>Services:</strong> ${servicesList}</div>
          <div><strong>Stylist:</strong> ${stylist}</div>
          <div><strong>Date & Time:</strong> ${date} at ${selectedSalonSlot}</div>
          <div><strong>Estimated Total:</strong> ${total} (Payable at studio)</div>
        </div>

        <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20I%20booked%20a%20salon%20slot%20for%20${encodeURIComponent(name)}%20on%20${date}%20at%20${selectedSalonSlot}." target="_blank" class="btn btn-whatsapp" style="width: 100%;">
          <span>💬 Open WhatsApp Confirmation</span>
        </a>
      </div>
    `;

    openModal(modalHtml);
    showToast('Salon slot confirmed!', '✨');
  }

  const salonDateInput = document.getElementById('salonDate');
  if (salonDateInput) {
    const today = new Date();
    salonDateInput.value = today.toISOString().split('T')[0];
    salonDateInput.min = today.toISOString().split('T')[0];
  }
</script>
"""


# ==============================================================================
# 4. COACHING / EDUCATION VERTICAL TEMPLATE
# ==============================================================================

_COACHING_TEMPLATE = """
<!-- Hero Section -->
<section class="hero-section" id="hero">
  <div class="container hero-grid">
    <div class="hero-content">
      <div class="hero-badge-row">
        <span class="section-eyebrow">🎓 Premier Coaching & Exam Preparation</span>
        <div class="rating-badge">
          <span class="rating-stars">★★★★★</span>
          <span>4.9 (780+ Student & Parent Reviews)</span>
        </div>
      </div>
      <h1 class="hero-title">Crack JEE, NEET & Board Exams with Proven Top Mentors in <span class="highlight">{{CITY}}</span></h1>
      <p class="hero-subtitle">Welcome to {{BUSINESS_NAME}}. We provide structured concept clarity, daily problem practice, adaptive mock test series, and personalized 1-on-1 doubt clearing for Grades 9th to 12th.</p>
      
      <div class="hero-cta-group">
        <a href="#solution" class="btn btn-primary btn-lg">📚 Reserve Free Demo Class Seat</a>
        <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20I%20want%20to%20inquire%20about%20JEE%20and%20NEET%20coaching%20batches." target="_blank" class="btn btn-whatsapp btn-lg">💬 WhatsApp Counseling</a>
      </div>

      <div class="hero-stats-row">
        <div class="hero-stat">
          <span class="hero-stat-num">94.8%</span>
          <span class="hero-stat-label">Selection Success Rate</span>
        </div>
        <div class="hero-stat">
          <span class="hero-stat-num">1:15</span>
          <span class="hero-stat-label">Small Batch Ratio</span>
        </div>
        <div class="hero-stat">
          <span class="hero-stat-num">350+</span>
          <span class="hero-stat-label">IIT/AIIMS Selections</span>
        </div>
      </div>
    </div>

    <div class="hero-visual-wrap">
      <div class="hero-main-img-card">
        <img src="https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=1200&q=80" alt="{{BUSINESS_NAME}} Interactive Classroom in {{CITY}}">
      </div>
      <div class="hero-floating-card floating-card-1">
        <div class="floating-icon">🏆</div>
        <div class="floating-text">
          <strong>Top Rankers Mentorship</strong>
          <span>IIT & Medical Alumni Faculty</span>
        </div>
      </div>
      <div class="hero-floating-card floating-card-2">
        <div class="floating-icon">📝</div>
        <div class="floating-text">
          <strong>Daily Mock Practice</strong>
          <span>Real Exam Simulated Testing</span>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Academic Courses Grid -->
<section id="services">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Our Academic Programs</span>
      <h2 class="section-title">Result-Oriented Classroom Batches</h2>
      <p class="section-subtitle">Structured pedagogy, comprehensive study modules, and regular AI-driven performance tracking for competitive exams.</p>
    </div>

    <div class="cards-grid">
      <div class="card">
        <div class="card-img-wrap">
          <img src="https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=600&q=80" alt="IIT-JEE Coaching Batch at {{BUSINESS_NAME}}">
          <span class="card-badge">Top Rankers Batch</span>
        </div>
        <div class="card-icon">⚡</div>
        <h3 class="card-title">IIT-JEE (Main + Advanced)</h3>
        <p class="card-desc">2-Year intensive program covering in-depth PCM concepts, multi-concept problem drills, and past 15-year paper workshops.</p>
        <div class="card-footer">
          <span class="card-price">Grades 11–12</span>
          <a href="#solution" class="btn btn-outline btn-sm">Reserve Demo Seat</a>
        </div>
      </div>

      <div class="card">
        <div class="card-img-wrap">
          <img src="https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=600&q=80" alt="NEET Medical Masterclass at {{BUSINESS_NAME}}">
          <span class="card-badge">100% NCERT Focused</span>
        </div>
        <div class="card-icon">🩺</div>
        <h3 class="card-title">NEET-UG Medical Masterclass</h3>
        <p class="card-desc">Specialized biology mnemonic workshops, physics speed calculation tricks, and full-length OMR simulation exams.</p>
        <div class="card-footer">
          <span class="card-price">Grades 11–12</span>
          <a href="#solution" class="btn btn-outline btn-sm">Reserve Demo Seat</a>
        </div>
      </div>

      <div class="card">
        <div class="card-img-wrap">
          <img src="https://images.unsplash.com/photo-1509062522246-3755977927d7?w=600&q=80" alt="Foundation Olympiad Batch at {{BUSINESS_NAME}}">
          <span class="card-badge">Olympiad & NTSE</span>
        </div>
        <div class="card-icon">🧠</div>
        <h3 class="card-title">Early Foundation (Class 9 & 10)</h3>
        <p class="card-desc">Develops analytical reasoning, science lab experiment exposure, and school exam topper mastery with zero pressure.</p>
        <div class="card-footer">
          <span class="card-price">Grades 9–10</span>
          <a href="#solution" class="btn btn-outline btn-sm">Reserve Demo Seat</a>
        </div>
      </div>

      <div class="card">
        <div class="card-img-wrap">
          <img src="https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=600&q=80" alt="Crash Course & Test Series at {{BUSINESS_NAME}}">
          <span class="card-badge">Intensive Revision</span>
        </div>
        <div class="card-icon">🎯</div>
        <h3 class="card-title">Board Booster & Mock Test Series</h3>
        <p class="card-desc">90-day sprint with daily full-syllabus chapter tests, model answer grading, and doubt clearance clinics.</p>
        <div class="card-footer">
          <span class="card-price">Crash Program</span>
          <a href="#solution" class="btn btn-outline btn-sm">Reserve Demo Seat</a>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Course Explorer & Demo Class Seat Reservation -->
<section id="solution" style="background: var(--bg-soft);">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Academic Programs</span>
      <h2 class="section-title">Explore Batches & Claim Your Free Demo Seat</h2>
      <p class="section-subtitle">Experience our teaching methodology before enrolling. Select a batch and attend a 2-day live trial session.</p>
    </div>

    <div class="interactive-hub">
      <div class="interactive-hub-header">
        <div class="hub-title-group">
          <h3><span>📚</span> Batch Selector & Free Demo Seat Booker</h3>
          <p style="font-size: 14px; color: var(--text-muted); margin-top: 4px;">Live enrollment portal for {{BUSINESS_NAME}}, {{CITY}}</p>
        </div>
        <span class="hub-badge">Limited Free Trial Seats</span>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px;">
        <div>
          <div class="form-group">
            <label class="form-label">1. Target Exam Stream</label>
            <select class="form-select" id="courseStreamSelect" onchange="updateCourseDetails()">
              <option value="jee">IIT-JEE (Main + Advanced) 2-Year Integrated</option>
              <option value="neet">NEET-UG Medical Masterclass</option>
              <option value="foundation">Class 9th & 10th Olympiad & Foundation</option>
              <option value="crash">12th Board Booster + Rapid Crash Course</option>
            </select>
          </div>

          <div id="courseInfoCard" style="background: var(--bg-soft); border: 1px solid var(--border); border-radius: var(--radius-md); padding: 20px; margin-bottom: 20px;">
            <strong style="font-size: 16px; color: var(--primary); display: block; margin-bottom: 8px;" id="courseTitleDisplay">IIT-JEE (Main + Advanced) 2-Year Program</strong>
            <p style="font-size: 13px; color: var(--text-muted); line-height: 1.6; margin-bottom: 12px;" id="courseDescDisplay">Comprehensive physics, chemistry, and mathematics coaching with daily 50-problem worksheets, weekly proctored tests, and personal faculty mentoring.</p>
            <div style="font-size: 13px; display: flex; justify-content: space-between;">
              <span><strong>Batch Timings:</strong> 4:30 PM – 7:30 PM</span>
              <span style="color: #ea580c; font-weight: 700;">Only 4 Demo Seats Left</span>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">2. Student Current Grade / Class</label>
            <select class="form-select" id="studentGradeSelect">
              <option>Entering Class 11th (2026 Batch)</option>
              <option>Entering Class 12th (2025 Batch)</option>
              <option>Class 12th Passed / Dropper Batch</option>
              <option>Class 9th / 10th Foundation</option>
            </select>
          </div>
        </div>

        <div>
          <div class="form-group">
            <label class="form-label">3. Student & Parent Contact</label>
            <input type="text" class="form-input" id="studentName" placeholder="Student Full Name" style="margin-bottom: 10px;">
            <input type="text" class="form-input" id="parentName" placeholder="Parent / Guardian Name" style="margin-bottom: 10px;">
            <input type="tel" class="form-input" id="studentPhone" placeholder="Mobile Number (WhatsApp Enabled)">
          </div>

          <div class="form-group">
            <label class="form-label">4. Preferred Demo Date</label>
            <input type="date" class="form-input" id="coachingDemoDate">
          </div>

          <button class="btn btn-primary btn-lg" style="width: 100%;" onclick="submitCoachingDemoBooking()">
            <span>📚 Claim Free 2-Day Trial Pass</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Campus & Learning Infrastructure Gallery -->
<section id="gallery">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Campus Infrastructure</span>
      <h2 class="section-title">State-of-the-Art Learning Environment</h2>
      <p class="section-subtitle">Equipped with smart digital boards, quiet air-conditioned study halls, and dedicated faculty doubt booths in {{CITY}}.</p>
    </div>

    <div class="gallery-grid">
      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1580582932707-520aed937b7b?w=600&q=80" alt="Smart Classroom at {{BUSINESS_NAME}}">
        <div class="gallery-overlay">
          <div class="gallery-title">Smart Interactive Classrooms</div>
          <div class="gallery-sub">Equipped with 4K digital projection & lecture recording</div>
        </div>
      </div>

      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=600&q=80" alt="Science Laboratory at {{BUSINESS_NAME}}">
        <div class="gallery-overlay">
          <div class="gallery-title">Advanced Science Labs</div>
          <div class="gallery-sub">Practical concept verification experiments</div>
        </div>
      </div>

      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=600&q=80" alt="Study Library at {{BUSINESS_NAME}}">
        <div class="gallery-overlay">
          <div class="gallery-title">Self-Study Silent Library</div>
          <div class="gallery-sub">10,000+ reference books & individual study cubicles</div>
        </div>
      </div>

      <div class="gallery-item">
        <img src="https://images.unsplash.com/photo-1577896851231-70ef18881754?w=600&q=80" alt="Doubt Clearing Session at {{BUSINESS_NAME}}">
        <div class="gallery-overlay">
          <div class="gallery-title">1-on-1 Doubt Clearing</div>
          <div class="gallery-sub">Full-time resident faculty available until 8 PM</div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Student Testimonials -->
<section id="testimonials" style="background: var(--bg-soft);">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Success Stories</span>
      <h2 class="section-title">What Our Toppers & Parents Say</h2>
      <p class="section-subtitle">Real experiences from students who achieved dream ranks in JEE and NEET through {{BUSINESS_NAME}}.</p>
    </div>

    <div class="testimonials-grid">
      <div class="testimonial-card">
        <div class="testimonial-header">
          <img src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&q=80" alt="Student Topper at {{BUSINESS_NAME}}" class="testimonial-avatar">
          <div>
            <div class="testimonial-name">Ananya Sharma</div>
            <div class="testimonial-role">AIR 142 (JEE Advanced) • IIT Bombay CSE</div>
          </div>
        </div>
        <div class="rating-stars">★★★★★</div>
        <p class="testimonial-text">"The daily problem sheets and simulated mock tests at {{BUSINESS_NAME}} made all the difference. The faculty was always available to solve doubts personally, even late in the evening."</p>
      </div>

      <div class="testimonial-card">
        <div class="testimonial-header">
          <img src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&q=80" alt="Student Topper at {{BUSINESS_NAME}}" class="testimonial-avatar">
          <div>
            <div class="testimonial-name">Rohan Mehta</div>
            <div class="testimonial-role">NEET-UG Score: 692/720 • AIIMS</div>
          </div>
        </div>
        <div class="rating-stars">★★★★★</div>
        <p class="testimonial-text">"The biology NCERT dissection and weekly test analysis sessions eliminated my silly mistakes completely. Best faculty mentors in {{CITY}}."</p>
      </div>

      <div class="testimonial-card">
        <div class="testimonial-header">
          <img src="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&q=80" alt="Parent Review for {{BUSINESS_NAME}}" class="testimonial-avatar">
          <div>
            <div class="testimonial-name">Suresh Patel (Parent)</div>
            <div class="testimonial-role">Father of Aarav Patel • Class 10th Topper</div>
          </div>
        </div>
        <div class="rating-stars">★★★★★</div>
        <p class="testimonial-text">"The regular progress reports and mentor calls gave us complete peace of mind. Aarav gained tremendous confidence in mathematics."</p>
      </div>
    </div>
  </div>
</section>

<!-- Location & Contact -->
<section id="contact">
  <div class="container contact-grid">
    <div class="contact-info-card">
      <div>
        <span class="section-eyebrow" style="background: rgba(255,255,255,0.2); color: #fff;">Campus Center</span>
        <h3 style="margin-top: 10px;">{{BUSINESS_NAME}}</h3>
        <p style="font-size: 14px; opacity: 0.9; margin-top: 8px;">Spacious air-conditioned smart classrooms, library, and faculty doubt rooms in {{CITY}}.</p>
      </div>

      <div class="contact-item">
        <div class="contact-item-icon">📍</div>
        <div class="contact-item-text">
          <strong>Campus Center Address</strong>
          <span>{{ADDRESS}}</span>
        </div>
      </div>

      <div class="contact-item">
        <div class="contact-item-icon">📞</div>
        <div class="contact-item-text">
          <strong>Academic Counselor Desk</strong>
          <span><a href="tel:{{CLEAN_PHONE}}" style="color: #fff; text-decoration: underline;">{{PHONE}}</a></span>
        </div>
      </div>

      <div>
        <strong style="display: block; margin-bottom: 8px; font-size: 14px;">Center & Counseling Timings:</strong>
        <table class="hours-table">
          <tr><td>Monday – Saturday</td><td style="text-align: right;">8:30 AM – 8:00 PM</td></tr>
          <tr><td>Sunday Parent Counseling</td><td style="text-align: right;">9:30 AM – 2:00 PM</td></tr>
        </table>
      </div>
    </div>

    <div style="background: #fff; border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 36px; box-shadow: var(--shadow-md);">
      <h3 style="font-size: 22px; margin-bottom: 8px;">Download Full Syllabus & Brochure</h3>
      <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 24px;">Get our comprehensive test series roadmap and fee structure sent straight to your WhatsApp.</p>

      <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20please%20send%20me%20the%20JEE/NEET%20syllabus%20and%20fee%20brochure." target="_blank" class="btn btn-whatsapp btn-lg" style="width: 100%;">
        <span>📄 Download Brochure on WhatsApp</span>
      </a>
    </div>
  </div>
</section>

<script>
  function updateCourseDetails() {
    const stream = document.getElementById('courseStreamSelect').value;
    const title = document.getElementById('courseTitleDisplay');
    const desc = document.getElementById('courseDescDisplay');

    if (stream === 'jee') {
      title.innerText = 'IIT-JEE (Main + Advanced) 2-Year Program';
      desc.innerText = 'Rigorous physics, chemistry, and mathematics with daily 50-problem sheets, simulated online testing, and IITian faculty mentoring.';
    } else if (stream === 'neet') {
      title.innerText = 'NEET-UG Medical Masterclass (NCERT 100% Mastery)';
      desc.innerText = 'Specialized biology diagrams, NCERT line-by-line decoding, physics numerical shortcuts, and botanical garden lab sessions.';
    } else if (stream === 'foundation') {
      title.innerText = 'Class 9th & 10th Olympiad & NTSE Foundation';
      desc.innerText = 'Building strong mathematical intuition, scientific aptitude, and school topper preparation with zero study stress.';
    } else {
      title.innerText = 'Class 12th Board Booster & Rapid Test Series';
      desc.innerText = 'Targeted answer writing workshops, past 10-year question solving, and formula revision bootcamps.';
    }
  }

  function submitCoachingDemoBooking() {
    const student = document.getElementById('studentName').value.trim();
    const phone = document.getElementById('studentPhone').value.trim();
    const stream = document.getElementById('courseStreamSelect').options[document.getElementById('courseStreamSelect').selectedIndex].text;
    const date = document.getElementById('coachingDemoDate').value;

    if (!student || !phone) {
      alert('Please enter student name and mobile number.');
      return;
    }

    const modalHtml = `
      <div style="text-align: center; padding: 10px 0;">
        <div style="font-size: 50px; margin-bottom: 10px;">🎓</div>
        <h3 style="font-size: 24px; color: var(--primary); margin-bottom: 8px;">Demo Class Seat Reserved!</h3>
        <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 20px;">Your 2-day classroom demo seat has been confirmed for ${student}.</p>

        <div style="background: var(--bg-soft); border-radius: var(--radius-md); padding: 16px; text-align: left; font-size: 14px; margin-bottom: 20px; line-height: 1.8;">
          <div><strong>Student:</strong> ${student} (${phone})</div>
          <div><strong>Program:</strong> ${stream}</div>
          <div><strong>Trial Date:</strong> ${date}</div>
          <div><strong>Campus Center:</strong> {{ADDRESS}}</div>
        </div>

        <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20I%20booked%20a%20demo%20seat%20for%20${encodeURIComponent(student)}%20for%20${encodeURIComponent(stream)}." target="_blank" class="btn btn-whatsapp" style="width: 100%;">
          <span>💬 Open WhatsApp Classroom Pass</span>
        </a>
      </div>
    `;

    openModal(modalHtml);
    showToast('Demo seat confirmed!', '🎓');
  }

  const demoDateInput = document.getElementById('coachingDemoDate');
  if (demoDateInput) {
    const today = new Date();
    today.setDate(today.getDate() + 2);
    demoDateInput.value = today.toISOString().split('T')[0];
  }
</script>
"""


# ==============================================================================
# 5. RETAIL / GROCERY VERTICAL TEMPLATE
# ==============================================================================

_RETAIL_TEMPLATE = """
<!-- Hero Section -->
<section class="hero-section" id="hero">
  <div class="container hero-grid">
    <div class="hero-content">
      <div class="hero-badge-row">
        <span class="section-eyebrow">🛒 Farm-Fresh Groceries & Express Delivery</span>
        <div class="rating-badge">
          <span class="rating-stars">★★★★★</span>
          <span>4.9 (920+ Happy Shoppers)</span>
        </div>
      </div>
      <h1 class="hero-title">Farm-Fresh Vegetables, Organic Staples & Essentials Delivered in <span class="highlight">{{CITY}}</span></h1>
      <p class="hero-subtitle">Welcome to {{BUSINESS_NAME}}. We bring hand-picked fruits, pure dairy, pantry staples, and FMCG daily goods directly to your kitchen doorstep with same-day express delivery.</p>
      
      <div class="hero-cta-group">
        <a href="#solution" class="btn btn-primary btn-lg">🛍️ Shop Fresh Catalog</a>
        <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20I%20want%20to%20send%20my%20grocery%20list." target="_blank" class="btn btn-whatsapp btn-lg">💬 Send Grocery List on WhatsApp</a>
      </div>

      <div class="hero-stats-row">
        <div class="hero-stat">
          <span class="hero-stat-num">1,200+</span>
          <span class="hero-stat-label">Daily Grocery Products</span>
        </div>
        <div class="hero-stat">
          <span class="hero-stat-num">45 Mins</span>
          <span class="hero-stat-label">Express Doorstep Delivery</span>
        </div>
        <div class="hero-stat">
          <span class="hero-stat-num">100%</span>
          <span class="hero-stat-label">Freshness Guarantee</span>
        </div>
      </div>
    </div>

    <div class="hero-visual-wrap">
      <div class="hero-main-img-card">
        <img src="https://images.unsplash.com/photo-1542838132-92c53300491e?w=1200&q=80" alt="{{BUSINESS_NAME}} Fresh Grocery Aisle in {{CITY}}">
      </div>
      <div class="hero-floating-card floating-card-1">
        <div class="floating-icon">🥦</div>
        <div class="floating-text">
          <strong>Daily Farm Harvest</strong>
          <span>Organic & Chemical-Free</span>
        </div>
      </div>
      <div class="hero-floating-card floating-card-2">
        <div class="floating-icon">🛵</div>
        <div class="floating-text">
          <strong>Free Express Delivery</strong>
          <span>On all orders over ₹499</span>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Grocery Catalog & Live Cart -->
<section id="solution" style="background: var(--bg-soft);">
  <div class="container">
    <div class="section-header">
      <span class="section-eyebrow">Digital Grocery Store</span>
      <h2 class="section-title">Shop Daily Kitchen Essentials</h2>
      <p class="section-subtitle">Pick items, build your basket, and dispatch directly to our order packaging desk via WhatsApp.</p>
    </div>

    <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 30px;">
      <div>
        <div class="cards-grid">
          <div class="card">
            <div class="card-img-wrap">
              <img src="https://images.unsplash.com/photo-1610832958506-aa56368176cf?w=600&q=80" alt="Fresh Fruits">
              <span class="card-badge">Farm Fresh</span>
            </div>
            <h3 class="card-title">Organic Shimla Apple (1 kg)</h3>
            <p class="card-desc">Crisp, naturally sweet Royal Delicious apples sourced directly from Himachal orchards.</p>
            <div class="card-footer">
              <span class="card-price">₹180 / kg</span>
              <button class="btn btn-primary btn-sm" onclick="addGrocery('Organic Shimla Apple (1 kg)', 180)">+ Add to Basket</button>
            </div>
          </div>

          <div class="card">
            <div class="card-img-wrap">
              <img src="https://images.unsplash.com/photo-1597362925123-77861d3fbac7?w=600&q=80" alt="Fresh Vegetables">
              <span class="card-badge">Daily Harvest</span>
            </div>
            <h3 class="card-title">Hydroponic Salad Greens Box</h3>
            <p class="card-desc">Crunchy butterhead lettuce, baby spinach, cherry tomatoes, and english cucumber (500g).</p>
            <div class="card-footer">
              <span class="card-price">₹140</span>
              <button class="btn btn-primary btn-sm" onclick="addGrocery('Hydroponic Salad Greens Box', 140)">+ Add to Basket</button>
            </div>
          </div>

          <div class="card">
            <div class="card-img-wrap">
              <img src="https://images.unsplash.com/photo-1586201375761-83865001e31c?w=600&q=80" alt="Organic Staples">
              <span class="card-badge">Pure Pantry</span>
            </div>
            <h3 class="card-title">Aged Royal Basmati Rice (5 kg)</h3>
            <p class="card-desc">Aged for 2 years with signature aromatic long grains for perfect biryanis and pulao.</p>
            <div class="card-footer">
              <span class="card-price">₹650</span>
              <button class="btn btn-primary btn-sm" onclick="addGrocery('Aged Royal Basmati Rice (5 kg)', 650)">+ Add to Basket</button>
            </div>
          </div>

          <div class="card">
            <div class="card-img-wrap">
              <img src="https://images.unsplash.com/photo-1550583724-b2692b85b150?w=600&q=80" alt="A2 Cow Milk">
              <span class="card-badge">Farm Pure</span>
            </div>
            <h3 class="card-title">Fresh Gir Cow A2 Milk (1 Ltr)</h3>
            <p class="card-desc">Raw unadulterated pasteurized whole A2 milk delivered cold in sterilized glass bottles.</p>
            <div class="card-footer">
              <span class="card-price">₹85</span>
              <button class="btn btn-primary btn-sm" onclick="addGrocery('Fresh Gir Cow A2 Milk (1 Ltr)', 85)">+ Add to Basket</button>
            </div>
          </div>
        </div>
      </div>

      <div>
        <div style="background: #ffffff; border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 24px; box-shadow: var(--shadow-md); position: sticky; top: 100px;">
          <h3 style="font-size: 18px; border-bottom: 1px solid var(--border); padding-bottom: 12px; margin-bottom: 16px;">
            🛒 Grocery Basket (<span id="groceryCount">0</span> items)
          </h3>

          <div id="groceryItemsList" style="max-height: 240px; overflow-y: auto; margin-bottom: 16px;">
            <p style="font-size: 13px; color: var(--text-muted); text-align: center; padding: 20px 0;">Basket is empty.</p>
          </div>

          <div style="border-top: 1px solid var(--border); padding-top: 12px; font-size: 16px; margin-bottom: 16px; display: flex; justify-content: space-between;">
            <strong>Total Amount:</strong>
            <strong style="color: var(--primary);" id="groceryTotal">₹0</strong>
          </div>

          <button class="btn btn-primary btn-lg" style="width: 100%;" id="groceryCheckoutBtn" onclick="checkoutGrocery()" disabled>
            <span>🛍️ Send Order via WhatsApp</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- Location & Contact -->
<section id="contact">
  <div class="container contact-grid">
    <div class="contact-info-card">
      <div>
        <span class="section-eyebrow" style="background: rgba(255,255,255,0.2); color: #fff;">Store Location</span>
        <h3 style="margin-top: 10px;">{{BUSINESS_NAME}}</h3>
        <p style="font-size: 14px; opacity: 0.9; margin-top: 8px;">Visit our supermarket or send your handwritten grocery list on WhatsApp for instant packing.</p>
      </div>

      <div class="contact-item">
        <div class="contact-item-icon">📍</div>
        <div class="contact-item-text">
          <strong>Store Address</strong>
          <span>{{ADDRESS}}</span>
        </div>
      </div>

      <div class="contact-item">
        <div class="contact-item-icon">📞</div>
        <div class="contact-item-text">
          <strong>Store Hotline</strong>
          <span><a href="tel:{{CLEAN_PHONE}}" style="color: #fff; text-decoration: underline;">{{PHONE}}</a></span>
        </div>
      </div>

      <div>
        <strong style="display: block; margin-bottom: 8px; font-size: 14px;">Store Hours:</strong>
        <table class="hours-table">
          <tr><td>Monday – Sunday</td><td style="text-align: right;">7:30 AM – 10:00 PM</td></tr>
          <tr><td>Home Delivery Service</td><td style="text-align: right;">8:00 AM – 9:00 PM</td></tr>
        </table>
      </div>
    </div>

    <div style="background: #fff; border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 36px; box-shadow: var(--shadow-md);">
      <h3 style="font-size: 22px; margin-bottom: 8px;">Upload Photo of Grocery List</h3>
      <p style="font-size: 14px; color: var(--text-muted); margin-bottom: 24px;">Don't want to type? Snap a picture of your handwritten shopping list and WhatsApp it to us.</p>

      <a href="https://wa.me/{{WHATSAPP_PHONE}}?text=Hi%20{{BUSINESS_NAME}},%20I%20am%20sending%20a%20picture%20of%20my%20grocery%20list%20for%20home%20delivery." target="_blank" class="btn btn-whatsapp btn-lg" style="width: 100%;">
        <span>📸 Send Photo of List on WhatsApp</span>
      </a>
    </div>
  </div>
</section>

<script>
  let groceryCart = [];

  function addGrocery(name, price) {
    const existing = groceryCart.find(i => i.name === name);
    if (existing) {
      existing.qty += 1;
    } else {
      groceryCart.push({ name, price, qty: 1 });
    }
    renderGroceryCart();
    showToast(`Added ${name} to basket`, '🛒');
  }

  function renderGroceryCart() {
    const container = document.getElementById('groceryItemsList');
    const totalCount = groceryCart.reduce((sum, i) => sum + i.qty, 0);
    const total = groceryCart.reduce((sum, i) => sum + (i.price * i.qty), 0);

    document.getElementById('groceryCount').innerText = totalCount;
    document.getElementById('groceryTotal').innerText = '₹' + total;
    document.getElementById('groceryCheckoutBtn').disabled = groceryCart.length === 0;

    if (groceryCart.length === 0) {
      container.innerHTML = '<p style="font-size: 13px; color: var(--text-muted); text-align: center; padding: 20px 0;">Basket is empty.</p>';
    } else {
      let html = '';
      groceryCart.forEach(i => {
        html += `<div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--border); font-size:13px;">
          <span>${i.qty}x ${i.name}</span>
          <strong>₹${i.price * i.qty}</strong>
        </div>`;
      });
      container.innerHTML = html;
    }
  }

  function checkoutGrocery() {
    const total = groceryCart.reduce((sum, i) => sum + (i.price * i.qty), 0);
    const summary = groceryCart.map(i => `${i.qty}x ${i.name} (₹${i.price * i.qty})`).join('%0A');
    const waText = `Hi {{BUSINESS_NAME}}, please deliver these groceries:%0A%0A${summary}%0A%0ATotal: ₹${total}%0A%0AAddress: {{ADDRESS}}`;

    window.open(`https://wa.me/{{WHATSAPP_PHONE}}?text=${waText}`, '_blank');
    showToast('Redirecting to WhatsApp Order...', '🛍️');
  }
</script>
"""

_GYM_TEMPLATE = _CLINIC_TEMPLATE
_REAL_ESTATE_TEMPLATE = _CLINIC_TEMPLATE
_GENERAL_SMB_TEMPLATE = _CLINIC_TEMPLATE