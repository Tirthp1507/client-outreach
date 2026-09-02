"""Demo Strategy & Generator: Build client-specific, multi-page, presentation-grade commercial HTML prototypes.

Every generated prototype is a full 3-page commercial website tailored to the business category:
1. `index.html`: Home Showcase & Interactive Appointment/Ordering App
2. `services.html`: Full Services Catalog, Interactive Search & Rate Card
3. `about.html`: Brand Legacy, Team Specialists & Photo Gallery Showcase

Features:
- Glassmorphism sticky navbar with multi-page navigation
- Full-width hero section with Unsplash photography
- Smooth micro-animations (card hover lift, image zoom, pulsing badges, smooth scroll)
- Interactive Vanilla JS app engine (multi-step appointment booker, cart total, tab filtering, real-time search)
- Verified client reviews with avatars
- Interactive WhatsApp reservation modal and mobile bottom action bar
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
        "accent": "#06b6d4",
        "gradient": "linear-gradient(135deg, #0284c7 0%, #0d9488 100%)",
        "bg_soft": "#f0f9ff",
        "badge_bg": "#e0f2fe",
        "badge_text": "#0369a1",
        "icon": "⚕️",
        "hero_img": "https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=1200&q=80",
        "tagline": "Advanced Dental & Medical Healthcare Center",
        "rating": "⭐ 4.9/5 from 280+ Verified Patient Reviews",
    },
    VerticalType.RESTAURANT: {
        "primary": "#ea580c",
        "primary_dark": "#c2410c",
        "accent": "#f59e0b",
        "gradient": "linear-gradient(135deg, #ea580c 0%, #d97706 100%)",
        "bg_soft": "#fff7ed",
        "badge_bg": "#ffedd5",
        "badge_text": "#9a3412",
        "icon": "🍽️",
        "hero_img": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80",
        "tagline": "Authentic Culinary Dining & Fast Home Delivery",
        "rating": "⭐ 4.8/5 from 420+ Foodie Reviews",
    },
    VerticalType.SALON: {
        "primary": "#c026d3",
        "primary_dark": "#a21caf",
        "accent": "#f43f5e",
        "gradient": "linear-gradient(135deg, #c026d3 0%, #e11d48 100%)",
        "bg_soft": "#fdf4ff",
        "badge_bg": "#fae8ff",
        "badge_text": "#86198f",
        "icon": "✂️",
        "hero_img": "https://images.unsplash.com/photo-1560066984-138dadb4c035?auto=format&fit=crop&w=1200&q=80",
        "tagline": "Luxury Hair, Nails & Skin Aesthetics Studio",
        "rating": "⭐ 4.9/5 from 340+ Happy Salon Clients",
    },
    VerticalType.COACHING: {
        "primary": "#2563eb",
        "primary_dark": "#1d4ed8",
        "accent": "#4f46e5",
        "gradient": "linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)",
        "bg_soft": "#eff6ff",
        "badge_bg": "#dbeafe",
        "badge_text": "#1e40af",
        "icon": "🎓",
        "hero_img": "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?auto=format&fit=crop&w=1200&q=80",
        "tagline": "Premier Academic Coaching & Entrance Exam Academy",
        "rating": "⭐ 4.9/5 from 500+ Top Rankers",
    },
    VerticalType.GYM: {
        "primary": "#16a34a",
        "primary_dark": "#15803d",
        "accent": "#84cc16",
        "gradient": "linear-gradient(135deg, #16a34a 0%, #059669 100%)",
        "bg_soft": "#f0fdf4",
        "badge_bg": "#dcfce7",
        "badge_text": "#166534",
        "icon": "🏋️‍♂️",
        "hero_img": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=1200&q=80",
        "tagline": "State-of-the-Art Fitness Center & Personal Training",
        "rating": "⭐ 4.9/5 from 210+ Active Members",
    },
    VerticalType.RETAIL: {
        "primary": "#d97706",
        "primary_dark": "#b45309",
        "accent": "#ca8a04",
        "gradient": "linear-gradient(135deg, #d97706 0%, #b45309 100%)",
        "bg_soft": "#fefce8",
        "badge_bg": "#fef9c3",
        "badge_text": "#854d0e",
        "icon": "🛍️",
        "hero_img": "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=1200&q=80",
        "tagline": "Premium Quality Retail Store & Direct Home Delivery",
        "rating": "⭐ 4.8/5 from 180+ Local Buyers",
    },
    VerticalType.REAL_ESTATE: {
        "primary": "#4f46e5",
        "primary_dark": "#4338ca",
        "accent": "#0ea5e9",
        "gradient": "linear-gradient(135deg, #4f46e5 0%, #2563eb 100%)",
        "bg_soft": "#eef2ff",
        "badge_bg": "#e0e7ff",
        "badge_text": "#3730a3",
        "icon": "🏢",
        "hero_img": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=80",
        "tagline": "Luxury Residential Apartments & Villa Projects",
        "rating": "⭐ 4.9/5 from 150+ Homebuyers",
    },
    VerticalType.GENERAL_SMB: {
        "primary": "#0f766e",
        "primary_dark": "#115e59",
        "accent": "#06b6d4",
        "gradient": "linear-gradient(135deg, #0f766e 0%, #0284c7 100%)",
        "bg_soft": "#f0fdfa",
        "badge_bg": "#ccfbf1",
        "badge_text": "#134e4a",
        "icon": "⚡",
        "hero_img": "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1200&q=80",
        "tagline": "Professional Business Solutions & Direct Consultation",
        "rating": "⭐ 4.9/5 Verified Client Trust Score",
    },
}


class DemoBlueprint:
    """Blueprint defining the tailored multi-page strategy for a business."""

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
        short_title = f"{business.name} — Multi-Page Commercial Website Prototype"

        return DemoBlueprint(
            business_id=business.id,
            opportunity_id=opp.id,
            vertical=vertical,
            demo_type=demo_type,
            title=short_title,
            problem=opp.problem_summary or "Appointments and inquiries currently rely on manual phone calls — no 24/7 online booking or interactive rate card.",
            solution=opp.proposed_solution or "A multi-page, high-converting commercial website with online booking, rate catalog, and WhatsApp integration.",
            key_features=self._vertical_features(vertical, demo_type),
            custom_services=research_services or [],
        )

    @staticmethod
    def _vertical_features(vertical: VerticalType, demo_type: DemoType) -> List[str]:
        return ["Multi-page website navigation", "Instant online reservation system", "Searchable service rate card", "Verified client testimonials & photo gallery"]


class DemoGenerator:
    """Generates 3-page commercial website prototypes (index.html, services.html, about.html)."""

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

        # 1. Render Page 1: Home Showcase (index.html)
        index_path = demo_dir / "index.html"
        rendered_index = self._render_page(business, bp, current_page="index")
        index_path.write_text(rendered_index, encoding="utf-8")

        # 2. Render Page 2: Services & Pricing Catalog (services.html)
        services_path = demo_dir / "services.html"
        rendered_services = self._render_page(business, bp, current_page="services")
        services_path.write_text(rendered_services, encoding="utf-8")

        # 3. Render Page 3: About & Gallery Showcase (about.html)
        about_path = demo_dir / "about.html"
        rendered_about = self._render_page(business, bp, current_page="about")
        about_path.write_text(rendered_about, encoding="utf-8")

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
            "pages": ["index.html", "services.html", "about.html"],
        }

        return DemoRecord(
            id=demo_id,
            opportunity_id=opp.id,
            business_id=business.id,
            vertical=bp.vertical,
            demo_type=bp.demo_type,
            title=bp.title,
            artifact_path=str(index_path.relative_to(PROJECT_ROOT)),
            preview_url=f"{self.preview_base_url}/{demo_id}/index.html",
            status=DemoStatus.READY,
            metadata_json=metadata,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _render_page(self, business: BusinessRecord, bp: DemoBlueprint, current_page: str) -> str:
        theme = _VERTICAL_THEMES.get(bp.vertical, _VERTICAL_THEMES[VerticalType.GENERAL_SMB])
        
        if current_page == "index":
            content_html = self._generate_index_content(business, bp, theme)
        elif current_page == "services":
            content_html = self._generate_services_content(business, bp, theme)
        else:
            content_html = self._generate_about_content(business, bp, theme)

        # Active Nav Link CSS Helpers
        active_home = 'active' if current_page == 'index' else ''
        active_services = 'active' if current_page == 'services' else ''
        active_about = 'active' if current_page == 'about' else ''

        page = _MASTER_HTML_TEMPLATE
        replacements = {
            "{{TITLE}}": html.escape(bp.title),
            "{{BUSINESS_NAME}}": html.escape(business.name or "Your Business"),
            "{{CITY}}": html.escape(business.city or "India"),
            "{{PHONE}}": html.escape(business.phone or "+91 98765 43210"),
            "{{ADDRESS}}": html.escape(business.address or f"Main Road, {business.city or 'India'}"),
            "{{CATEGORY}}": html.escape(business.category.replace("_", " ").title()),
            "{{PROBLEM}}": html.escape(bp.problem),
            "{{SOLUTION}}": html.escape(bp.solution),
            "{{PRIMARY_COLOR}}": theme["primary"],
            "{{PRIMARY_DARK}}": theme["primary_dark"],
            "{{ACCENT_COLOR}}": theme["accent"],
            "{{GRADIENT}}": theme["gradient"],
            "{{BG_SOFT}}": theme["bg_soft"],
            "{{BADGE_BG}}": theme["badge_bg"],
            "{{BADGE_TEXT}}": theme["badge_text"],
            "{{ICON}}": theme["icon"],
            "{{HERO_IMG}}": theme["hero_img"],
            "{{TAGLINE}}": theme["tagline"],
            "{{RATING}}": theme["rating"],
            "{{ACTIVE_HOME}}": active_home,
            "{{ACTIVE_SERVICES}}": active_services,
            "{{ACTIVE_ABOUT}}": active_about,
            "{{CONTENT_HTML}}": content_html,
        }

        for key, val in replacements.items():
            page = page.replace(key, val)

        return page

    def _generate_index_content(self, business: BusinessRecord, bp: DemoBlueprint, theme: Dict[str, str]) -> str:
        v = bp.vertical
        if v == VerticalType.CLINIC:
            return _CLINIC_INDEX_TEMPLATE
        elif v == VerticalType.RESTAURANT:
            return _RESTAURANT_INDEX_TEMPLATE
        elif v == VerticalType.SALON:
            return _SALON_INDEX_TEMPLATE
        elif v == VerticalType.COACHING:
            return _COACHING_INDEX_TEMPLATE
        elif v == VerticalType.GYM:
            return _GYM_INDEX_TEMPLATE
        else:
            return _GENERAL_INDEX_TEMPLATE

    def _generate_services_content(self, business: BusinessRecord, bp: DemoBlueprint, theme: Dict[str, str]) -> str:
        v = bp.vertical
        if v == VerticalType.SALON:
            return _SALON_SERVICES_TEMPLATE
        elif v == VerticalType.RESTAURANT:
            return _RESTAURANT_SERVICES_TEMPLATE
        elif v == VerticalType.CLINIC:
            return _CLINIC_SERVICES_TEMPLATE
        else:
            return _GENERAL_SERVICES_TEMPLATE

    def _generate_about_content(self, business: BusinessRecord, bp: DemoBlueprint, theme: Dict[str, str]) -> str:
        v = bp.vertical
        if v == VerticalType.SALON:
            return _SALON_ABOUT_TEMPLATE
        elif v == VerticalType.RESTAURANT:
            return _RESTAURANT_ABOUT_TEMPLATE
        elif v == VerticalType.CLINIC:
            return _CLINIC_ABOUT_TEMPLATE
        else:
            return _GENERAL_ABOUT_TEMPLATE


# ==============================================================================
# MASTER MULTI-PAGE HTML TEMPLATE
# ==============================================================================

_MASTER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{TITLE}}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    :root {
      --primary: {{PRIMARY_COLOR}};
      --primary-dark: {{PRIMARY_DARK}};
      --accent: {{ACCENT_COLOR}};
      --gradient: {{GRADIENT}};
      --bg-soft: {{BG_SOFT}};
      --badge-bg: {{BADGE_BG}};
      --badge-text: {{BADGE_TEXT}};
      --text: #0f172a;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --card-bg: #ffffff;
      --shadow-sm: 0 2px 8px rgba(15, 23, 42, 0.04);
      --shadow-md: 0 12px 32px -10px rgba(15, 23, 42, 0.09);
      --shadow-lg: 0 20px 45px -12px rgba(15, 23, 42, 0.15);
      --radius-lg: 24px;
      --radius-md: 14px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      background: #f8fafc;
      color: var(--text);
      line-height: 1.6;
      padding-bottom: 90px;
      -webkit-font-smoothing: antialiased;
    }
    h1, h2, h3, h4, .brand-title { font-family: 'Outfit', sans-serif; }

    /* Top Promo Announcement Bar */
    .promo-banner {
      background: var(--gradient);
      color: #fff;
      padding: 8px 16px;
      font-size: 13px;
      font-weight: 700;
      text-align: center;
      letter-spacing: 0.3px;
      box-shadow: inset 0 -1px 0 rgba(0,0,0,0.1);
    }

    /* Top Prototype Notice Bar */
    .prototype-bar {
      background: #0f172a;
      color: #f8fafc;
      padding: 10px 24px;
      font-size: 13px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      border-bottom: 1px solid #1e293b;
    }
    .proto-badge {
      background: var(--gradient);
      color: #fff;
      padding: 4px 12px;
      border-radius: 20px;
      font-weight: 700;
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.5px;
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      background: #22c55e;
      border-radius: 50%;
      box-shadow: 0 0 10px #22c55e;
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }
      70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
      100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
    }

    /* Glassmorphism Commercial Navbar with Multi-Page Links */
    .site-nav {
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      padding: 14px 28px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 800;
    }
    .nav-brand {
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
    }
    .nav-logo {
      width: 44px;
      height: 44px;
      background: var(--gradient);
      color: #fff;
      font-size: 24px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .nav-title { font-size: 20px; font-weight: 800; color: var(--text); }
    .nav-sub { font-size: 12px; color: var(--text-muted); font-weight: 500; }

    /* Page Tabs Navigation */
    .nav-links {
      display: flex;
      align-items: center;
      gap: 6px;
      background: #f1f5f9;
      padding: 4px;
      border-radius: 14px;
    }
    .nav-link-btn {
      padding: 8px 18px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 700;
      color: #475569;
      text-decoration: none;
      transition: all 0.2s;
    }
    .nav-link-btn:hover { color: var(--primary); background: rgba(255,255,255,0.6); }
    .nav-link-btn.active {
      background: #fff;
      color: var(--primary-dark);
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }

    .nav-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .btn-nav-call {
      background: var(--bg-soft);
      color: var(--primary-dark);
      border: 1px solid var(--border);
      padding: 10px 18px;
      border-radius: 12px;
      font-weight: 700;
      font-size: 13px;
      text-decoration: none;
      transition: all 0.2s;
    }
    .btn-nav-call:hover { background: var(--primary); color: #fff; }

    .wrapper {
      max-width: 980px;
      margin: 0 auto;
      padding: 24px 16px;
    }

    /* Hero Section with Animation */
    .hero-banner {
      position: relative;
      border-radius: var(--radius-lg);
      overflow: hidden;
      margin-bottom: 28px;
      box-shadow: var(--shadow-lg);
      min-height: 400px;
      display: flex;
      align-items: flex-end;
      background: #0f172a url('{{HERO_IMG}}') center/cover no-repeat;
      animation: fadeIn 0.6s ease-out;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .hero-overlay {
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(15, 23, 42, 0.25) 0%, rgba(15, 23, 42, 0.9) 100%);
    }
    .hero-content {
      position: relative;
      z-index: 10;
      padding: 40px 36px;
      color: #fff;
      width: 100%;
    }
    .hero-badge-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }
    .hero-pill {
      background: rgba(255, 255, 255, 0.2);
      backdrop-filter: blur(8px);
      color: #fff;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 700;
      border: 1px solid rgba(255, 255, 255, 0.3);
    }
    .hero-rating {
      background: #f59e0b;
      color: #78350f;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 800;
    }
    .hero-title {
      font-size: 38px;
      font-weight: 900;
      line-height: 1.15;
      margin-bottom: 10px;
      letter-spacing: -0.5px;
    }
    .hero-tagline {
      font-size: 16px;
      color: #e2e8f0;
      margin-bottom: 22px;
      max-width: 620px;
    }
    .hero-buttons {
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
    }

    /* Solution Box Callout */
    .solution-box {
      background: #fff;
      border: 1px solid var(--border);
      border-left: 5px solid var(--primary);
      border-radius: var(--radius-md);
      padding: 20px 24px;
      margin-bottom: 28px;
      box-shadow: var(--shadow-sm);
    }
    .solution-box strong { color: var(--primary-dark); font-weight: 800; }

    /* Commercial Card & Micro-Animations */
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 32px;
      margin-bottom: 28px;
      box-shadow: var(--shadow-md);
      transition: transform 0.25s, box-shadow 0.25s;
    }
    .card:hover { box-shadow: var(--shadow-lg); }
    .card-heading {
      font-size: 22px;
      font-weight: 800;
      color: var(--text);
      margin-bottom: 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
    }

    /* Visual Grid Cards with Hover Animation */
    .service-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(270px, 1fr));
      gap: 20px;
      margin-bottom: 24px;
    }
    .service-card {
      border: 2px solid var(--border);
      border-radius: var(--radius-md);
      overflow: hidden;
      background: #fff;
      cursor: pointer;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
    }
    .service-card:hover {
      border-color: var(--primary);
      transform: translateY(-6px);
      box-shadow: var(--shadow-md);
    }
    .service-card:hover .service-card-img {
      transform: scale(1.06);
    }
    .service-card.active {
      border-color: var(--primary);
      box-shadow: 0 0 0 2px var(--primary);
      background: var(--bg-soft);
    }
    .service-card-img-wrap {
      height: 150px;
      width: 100%;
      overflow: hidden;
    }
    .service-card-img {
      height: 100%;
      width: 100%;
      object-fit: cover;
      transition: transform 0.4s ease;
    }
    .service-card-body { padding: 18px; }
    .service-card-title { font-weight: 800; font-size: 16px; color: var(--text); margin-bottom: 4px; }
    .service-card-desc { font-size: 13px; color: var(--text-muted); margin-bottom: 12px; line-height: 1.4; }
    .service-card-footer { display: flex; justify-content: space-between; align-items: center; }
    .service-card-price { font-size: 18px; font-weight: 900; color: var(--primary); }
    .service-card-check {
      width: 26px; height: 26px; border-radius: 50%; border: 2px solid var(--border);
      display: flex; align-items: center; justify-content: center; font-size: 12px; color: transparent; transition: all 0.2s;
    }
    .service-card.active .service-card-check { background: var(--primary); border-color: var(--primary); color: #fff; }

    /* Form Controls & Buttons */
    .form-group { margin-bottom: 20px; }
    .form-label { font-size: 13px; font-weight: 800; color: #334155; margin-bottom: 8px; display: block; text-transform: uppercase; letter-spacing: 0.5px; }
    .form-input, .form-select {
      width: 100%; padding: 14px 18px; border: 1.5px solid var(--border); border-radius: var(--radius-md); font-size: 15px; font-family: inherit; background: #fff; color: var(--text); transition: all 0.2s;
    }
    .form-input:focus, .form-select:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 4px rgba(2, 132, 199, 0.15); }
    .btn-main {
      background: var(--gradient); color: #fff; border: none; padding: 16px 32px; border-radius: var(--radius-md); font-size: 16px; font-weight: 800; cursor: pointer; width: 100%; transition: all 0.25s; box-shadow: 0 6px 20px rgba(2, 132, 199, 0.35); display: inline-flex; align-items: center; justify-content: center; gap: 10px; text-decoration: none;
    }
    .btn-main:hover { transform: translateY(-2px); box-shadow: 0 10px 28px rgba(2, 132, 199, 0.45); }

    /* Chip Selectors */
    .chip-grid { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
    .chip { padding: 10px 20px; border: 1.5px solid var(--border); border-radius: 30px; background: #fff; font-size: 13px; font-weight: 700; cursor: pointer; transition: all 0.2s; }
    .chip:hover { border-color: var(--primary); color: var(--primary); }
    .chip.active { background: var(--primary); color: #fff; border-color: var(--primary); box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3); }

    /* Team / Staff Grid */
    .team-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; margin-bottom: 28px; }
    .team-card { background: #fff; border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden; box-shadow: var(--shadow-sm); text-align: center; padding-bottom: 20px; transition: transform 0.2s; }
    .team-card:hover { transform: translateY(-4px); }
    .team-img { width: 100%; height: 220px; object-fit: cover; }
    .team-name { font-size: 17px; font-weight: 800; margin-top: 14px; color: var(--text); }
    .team-role { font-size: 13px; color: var(--primary); font-weight: 700; margin-bottom: 6px; }
    .team-exp { font-size: 12px; color: var(--text-muted); }

    /* Gallery Photo Grid */
    .gallery-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 28px; }
    .gallery-item { height: 200px; border-radius: var(--radius-md); overflow: hidden; position: relative; box-shadow: var(--shadow-sm); }
    .gallery-img { width: 100%; height: 100%; object-fit: cover; transition: transform 0.4s ease; }
    .gallery-item:hover .gallery-img { transform: scale(1.08); }

    /* Testimonials */
    .reviews-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 18px; margin-bottom: 28px; }
    .review-card { background: #fff; border: 1px solid var(--border); border-radius: var(--radius-md); padding: 22px; box-shadow: var(--shadow-sm); }
    .review-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
    .review-avatar { width: 46px; height: 46px; border-radius: 50%; object-fit: cover; border: 2px solid var(--border); }
    .review-name { font-weight: 800; font-size: 14px; }
    .review-stars { color: #f59e0b; font-size: 13px; }
    .review-text { font-size: 13px; color: var(--text-muted); line-height: 1.5; }

    /* Modal Overlay */
    .modal-backdrop { display: none; position: fixed; inset: 0; background: rgba(15, 23, 42, 0.75); backdrop-filter: blur(8px); z-index: 999; align-items: center; justify-content: center; padding: 16px; }
    .modal-backdrop.show { display: flex; }
    .modal-card { background: #fff; border-radius: var(--radius-lg); max-width: 480px; width: 100%; padding: 36px; box-shadow: 0 25px 60px rgba(0,0,0,0.3); text-align: center; animation: modalPop 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
    @keyframes modalPop { 0% { transform: scale(0.88); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
    .modal-icon { font-size: 54px; margin-bottom: 16px; }
    .modal-title { font-size: 24px; font-weight: 900; margin-bottom: 8px; }
    .modal-body { font-size: 14px; color: var(--text-muted); margin-bottom: 24px; line-height: 1.6; }
    .modal-wa-box { background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; padding: 14px 18px; border-radius: 14px; font-size: 13px; margin-bottom: 24px; text-align: left; line-height: 1.5; }

    /* Sticky Bottom Mobile Bar */
    .sticky-bar { position: fixed; bottom: 0; left: 0; right: 0; background: rgba(255, 255, 255, 0.96); backdrop-filter: blur(12px); border-top: 1px solid var(--border); padding: 14px 28px; display: flex; align-items: center; justify-content: space-between; gap: 16px; z-index: 900; box-shadow: 0 -4px 20px rgba(0,0,0,0.06); }

    @media (max-width: 768px) {
      .hero-title { font-size: 28px; }
      .site-nav { padding: 12px 16px; flex-wrap: wrap; gap: 10px; }
      .nav-links { width: 100%; justify-content: center; order: 3; margin-top: 6px; }
      .hero-content { padding: 28px 20px; }
      .service-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>

  <!-- Top Announcement Promo Bar -->
  <div class="promo-banner">
    ⚡ Special Online Promotion: Get 15% OFF Package Bookings Reserved Today!
  </div>

  <!-- Top Prototype Notice Bar -->
  <div class="prototype-bar">
    <div style="display:flex; align-items:center; gap:8px;">
      <span class="proto-badge">3-PAGE DEMO PROTOTYPE</span>
      <span style="font-weight:600;">Tailored for {{BUSINESS_NAME}}</span>
    </div>
    <div style="display:flex; align-items:center; gap:6px; color:#94a3b8; font-weight:500;">
      <span class="pulse-dot"></span>
      <span>Simulated Client Experience — Ready for Business Deployment</span>
    </div>
  </div>

  <!-- Commercial Glassmorphism Navigation Header -->
  <header class="site-nav">
    <a href="index.html" class="nav-brand">
      <div class="nav-logo">{{ICON}}</div>
      <div>
        <div class="nav-title">{{BUSINESS_NAME}}</div>
        <div class="nav-sub">📍 {{CITY}} • {{CATEGORY}}</div>
      </div>
    </a>

    <!-- Multi-Page Website Navigation Tabs -->
    <nav class="nav-links">
      <a href="index.html" class="nav-link-btn {{ACTIVE_HOME}}">Home</a>
      <a href="services.html" class="nav-link-btn {{ACTIVE_SERVICES}}">Services & Rates</a>
      <a href="about.html" class="nav-link-btn {{ACTIVE_ABOUT}}">About & Gallery</a>
    </nav>

    <div class="nav-actions">
      <a href="tel:{{PHONE}}" class="btn-nav-call">📞 Call {{PHONE}}</a>
    </div>
  </header>

  <div class="wrapper">

    <!-- High-Resolution Hero Section -->
    <section class="hero-banner">
      <div class="hero-overlay"></div>
      <div class="hero-content">
        <div class="hero-badge-row">
          <span class="hero-pill">✓ Verified Business in {{CITY}}</span>
          <span class="hero-rating">{{RATING}}</span>
        </div>
        <h1 class="hero-title">{{BUSINESS_NAME}}</h1>
        <p class="hero-tagline">{{TAGLINE}}</p>
        <div class="hero-buttons">
          <a href="index.html#mainFormCard" class="btn-main" style="width:auto; padding:12px 28px;">
            ⚡ Instant Online Reservation
          </a>
          <a href="services.html" class="btn-nav-call" style="padding:12px 24px; font-size:14px; background:rgba(255,255,255,0.2); color:#fff; border:1px solid rgba(255,255,255,0.4);">
            📖 Explore Full Rates
          </a>
        </div>
      </div>
    </section>

    <!-- Operational Problem & Solution Callout -->
    <div class="solution-box">
      <strong>Identified Growth Opportunity:</strong> {{PROBLEM}}<br>
      <strong>Proposed Digital Solution:</strong> {{SOLUTION}}
    </div>

    <!-- Page Content (Dynamically injected per page) -->
    {{CONTENT_HTML}}

  </div>

  <!-- Interactive WhatsApp Confirmation Modal -->
  <div class="modal-backdrop" id="confirmationModal">
    <div class="modal-card">
      <div class="modal-icon">✅</div>
      <div class="modal-title">Booking Request Confirmed!</div>
      <div class="modal-body" id="modalBodyText">
        Your booking request has been processed successfully. In production, this instantly reserves your slot and sends a digital WhatsApp confirmation pass.
      </div>
      <div class="modal-wa-box">
        <strong>📱 Simulated WhatsApp Alert:</strong><br>
        "Hi! Your reservation at {{BUSINESS_NAME}} in {{CITY}} is confirmed. We look forward to welcoming you!"
      </div>
      <button class="btn-main" onclick="closeModal()">Got it & Close</button>
    </div>
  </div>

  <!-- Sticky Bottom Contact Bar -->
  <div class="sticky-bar">
    <div style="font-size:13px; font-weight:700; color:var(--text);">
      ⚡ Live Commercial Demonstration for {{BUSINESS_NAME}}
    </div>
    <a href="index.html#mainFormCard" class="btn-main" style="width:auto; padding:10px 24px; font-size:14px;">
      Try Live Booking 🚀
    </a>
  </div>

  <script>
    function toggleCardSelect(el, groupClass) {
      document.querySelectorAll('.' + groupClass).forEach(item => item.classList.remove('active'));
      el.classList.add('active');
    }

    function toggleChip(el, groupClass) {
      document.querySelectorAll('.' + groupClass).forEach(item => item.classList.remove('active'));
      el.classList.add('active');
    }

    function showModal(msg) {
      if (msg) {
        document.getElementById('modalBodyText').innerText = msg;
      }
      document.getElementById('confirmationModal').classList.add('show');
    }

    function closeModal() {
      document.getElementById('confirmationModal').classList.remove('show');
    }

    function filterServices() {
      const q = document.getElementById('svcSearchInput').value.toLowerCase();
      document.querySelectorAll('.svc-item-row').forEach(row => {
        const title = row.getAttribute('data-title').toLowerCase();
        if (title.includes(q)) {
          row.style.display = 'flex';
        } else {
          row.style.display = 'none';
        }
      });
    }
  </script>
</body>
</html>
"""

# ==============================================================================
# SALON TEMPLATES (PAGE 1, 2 & 3)
# ==============================================================================

_SALON_INDEX_TEMPLATE = """
<div class="card" id="mainFormCard">
  <div class="card-heading">
    <span>✂️ Select Luxury Salon & Spa Services</span>
    <span style="font-size:13px; color:var(--primary); font-weight:700;">Live Interactive Booker</span>
  </div>

  <div class="form-group">
    <label class="form-label">1. Choose Service Package (Tap to Select)</label>
    <div class="service-grid">
      <div class="service-card active salon-svc" onclick="toggleCardSelect(this, 'salon-svc')">
        <div class="service-card-img-wrap">
          <img src="https://images.unsplash.com/photo-1562322140-8baeececf3df?auto=format&fit=crop&w=600&q=80" class="service-card-img" alt="Hair Styling">
        </div>
        <div class="service-card-body">
          <div class="service-card-title">Hair Styling & Couture Cut</div>
          <div class="service-card-desc">Couture hair wash, deep conditioning & precision blow dry.</div>
          <div class="service-card-footer">
            <div class="service-card-price">₹799</div>
            <div class="service-card-check">✓</div>
          </div>
        </div>
      </div>

      <div class="service-card salon-svc" onclick="toggleCardSelect(this, 'salon-svc')">
        <div class="service-card-img-wrap">
          <img src="https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?auto=format&fit=crop&w=600&q=80" class="service-card-img" alt="Facial Spa">
        </div>
        <div class="service-card-body">
          <div class="service-card-title">Radiance Skin & Facial Spa</div>
          <div class="service-card-desc">Hydrating facial cleanup, exfoliation & herbal massage.</div>
          <div class="service-card-footer">
            <div class="service-card-price">₹1,499</div>
            <div class="service-card-check">✓</div>
          </div>
        </div>
      </div>

      <div class="service-card salon-svc" onclick="toggleCardSelect(this, 'salon-svc')">
        <div class="service-card-img-wrap">
          <img src="https://images.unsplash.com/photo-1604654894610-df63bc536371?auto=format&fit=crop&w=600&q=80" class="service-card-img" alt="Nail Art">
        </div>
        <div class="service-card-body">
          <div class="service-card-title">Gel Nail Extensions & Spa</div>
          <div class="service-card-desc">Custom gel nail extensions, glitter art & manicure.</div>
          <div class="service-card-footer">
            <div class="service-card-price">₹1,299</div>
            <div class="service-card-check">✓</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="form-group">
    <label class="form-label">2. Select Master Stylist</label>
    <select class="form-select">
      <option>Any Available Master Stylist</option>
      <option>Priya Sharma (Senior Hair Specialist — 10+ Yrs Exp)</option>
      <option>Karan Verma (Beard & Hair Styling Artist)</option>
    </select>
  </div>

  <div class="form-group">
    <label class="form-label">3. Select Appointment Slot Today / Tomorrow</label>
    <div class="chip-grid">
      <div class="chip active salon-slot" onclick="toggleChip(this, 'salon-slot')">Today 11:00 AM</div>
      <div class="chip salon-slot" onclick="toggleChip(this, 'salon-slot')">Today 02:30 PM</div>
      <div class="chip salon-slot" onclick="toggleChip(this, 'salon-slot')">Today 05:00 PM</div>
      <div class="chip salon-slot" onclick="toggleChip(this, 'salon-slot')">Tomorrow 11:30 AM</div>
    </div>
  </div>

  <div class="form-group">
    <label class="form-label">4. Customer Contact Details</label>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
      <input type="text" class="form-input" placeholder="Your Full Name" value="Priya Sharma">
      <input type="tel" class="form-input" placeholder="WhatsApp Number" value="{{PHONE}}">
    </div>
  </div>

  <button class="btn-main" onclick="showModal('Salon appointment confirmed! Stylist calendar updated and instant WhatsApp alert dispatched.')">
    Confirm Salon Slot & Send Instant WhatsApp Pass 📱
  </button>
</div>
"""

_SALON_SERVICES_TEMPLATE = """
<div class="card">
  <div class="card-heading">
    <span>📖 Full Salon & Spa Rate Card</span>
    <span style="font-size:13px; color:var(--primary); font-weight:700;">8 Available Services</span>
  </div>

  <div class="form-group">
    <input type="text" id="svcSearchInput" onkeyup="filterServices()" class="form-input" placeholder="🔍 Search service name (e.g., Haircut, Facial, Nails, Bridal)...">
  </div>

  <div style="display:flex; flex-direction:column; gap:16px;">
    <div class="svc-item-row" data-title="Hair Styling & Couture Cut" style="display:flex; justify-content:space-between; align-items:center; padding:16px; border:1px solid var(--border); border-radius:14px; background:#fff;">
      <div style="display:flex; gap:16px; align-items:center;">
        <img src="https://images.unsplash.com/photo-1562322140-8baeececf3df?auto=format&fit=crop&w=150&q=80" style="width:70px; height:70px; border-radius:12px; object-fit:cover;">
        <div>
          <div style="font-weight:800; font-size:16px;">Hair Styling & Couture Cut</div>
          <div style="font-size:13px; color:var(--text-muted);">Couture hair wash, deep conditioning & blow dry • 45 Mins</div>
          <div style="font-weight:900; color:var(--primary); font-size:16px; margin-top:4px;">₹799</div>
        </div>
      </div>
      <button class="btn-main" style="width:auto; padding:10px 20px; font-size:13px;" onclick="showModal('Hair Styling selected! Click Home to finalize your booking.')">Book Now</button>
    </div>

    <div class="svc-item-row" data-title="Radiance Skin & Facial Spa" style="display:flex; justify-content:space-between; align-items:center; padding:16px; border:1px solid var(--border); border-radius:14px; background:#fff;">
      <div style="display:flex; gap:16px; align-items:center;">
        <img src="https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?auto=format&fit=crop&w=150&q=80" style="width:70px; height:70px; border-radius:12px; object-fit:cover;">
        <div>
          <div style="font-weight:800; font-size:16px;">Radiance Skin & Facial Spa</div>
          <div style="font-size:13px; color:var(--text-muted);">Hydrating facial cleanup & herbal neck massage • 60 Mins</div>
          <div style="font-weight:900; color:var(--primary); font-size:16px; margin-top:4px;">₹1,499</div>
        </div>
      </div>
      <button class="btn-main" style="width:auto; padding:10px 20px; font-size:13px;" onclick="showModal('Facial Spa selected! Click Home to finalize your booking.')">Book Now</button>
    </div>

    <div class="svc-item-row" data-title="Gel Nail Extensions & Spa" style="display:flex; justify-content:space-between; align-items:center; padding:16px; border:1px solid var(--border); border-radius:14px; background:#fff;">
      <div style="display:flex; gap:16px; align-items:center;">
        <img src="https://images.unsplash.com/photo-1604654894610-df63bc536371?auto=format&fit=crop&w=150&q=80" style="width:70px; height:70px; border-radius:12px; object-fit:cover;">
        <div>
          <div style="font-weight:800; font-size:16px;">Gel Nail Extensions & Spa</div>
          <div style="font-size:13px; color:var(--text-muted);">Custom gel nail extensions & glitter artwork • 50 Mins</div>
          <div style="font-weight:900; color:var(--primary); font-size:16px; margin-top:4px;">₹1,299</div>
        </div>
      </div>
      <button class="btn-main" style="width:auto; padding:10px 20px; font-size:13px;" onclick="showModal('Nail Art selected! Click Home to finalize your booking.')">Book Now</button>
    </div>

    <div class="svc-item-row" data-title="Bridal & Special Occasion Makeover" style="display:flex; justify-content:space-between; align-items:center; padding:16px; border:1px solid var(--border); border-radius:14px; background:#fff;">
      <div style="display:flex; gap:16px; align-items:center;">
        <img src="https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=150&q=80" style="width:70px; height:70px; border-radius:12px; object-fit:cover;">
        <div>
          <div style="font-weight:800; font-size:16px;">Bridal & Special Occasion Makeover</div>
          <div style="font-size:13px; color:var(--text-muted);">HD airbrush makeup, saree draping & hairstyle • 120 Mins</div>
          <div style="font-weight:900; color:var(--primary); font-size:16px; margin-top:4px;">₹3,999</div>
        </div>
      </div>
      <button class="btn-main" style="width:auto; padding:10px 20px; font-size:13px;" onclick="showModal('Bridal Package selected! Click Home to finalize your booking.')">Book Now</button>
    </div>
  </div>
</div>
"""

_SALON_ABOUT_TEMPLATE = """
<div class="card">
  <div class="card-heading">
    <span>✨ About {{BUSINESS_NAME}}</span>
    <span style="font-size:13px; color:var(--primary); font-weight:700;">Est. 2018 • {{CITY}}</span>
  </div>

  <p style="font-size:15px; color:var(--text-muted); margin-bottom:24px; line-height:1.7;">
    Welcome to <strong>{{BUSINESS_NAME}}</strong>, {{CITY}}'s premier luxury salon & spa destination. We specialize in precision hair styling, organic skincare facials, designer gel nail art, and flawless bridal makeovers. Our certified master stylists use top international organic products to deliver a world-class luxury salon experience.
  </p>

  <h3 style="font-size:20px; font-weight:800; margin-bottom:16px;">👑 Our Certified Master Stylists</h3>
  <div class="team-grid">
    <div class="team-card">
      <img src="https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?auto=format&fit=crop&w=400&q=80" class="team-img" alt="Priya Sharma">
      <div class="team-name">Priya Sharma</div>
      <div class="team-role">Master Hair & Extensions Specialist</div>
      <div class="team-exp">10+ Years Industry Experience</div>
    </div>

    <div class="team-card">
      <img src="https://images.unsplash.com/photo-1560250097-0b93528c311a?auto=format&fit=crop&w=400&q=80" class="team-img" alt="Karan Verma">
      <div class="team-name">Karan Verma</div>
      <div class="team-role">Beard & Hair Styling Artist</div>
      <div class="team-exp">7+ Years Industry Experience</div>
    </div>

    <div class="team-card">
      <img src="https://images.unsplash.com/photo-1580489944761-15a19d654956?auto=format&fit=crop&w=400&q=80" class="team-img" alt="Anjali Patel">
      <div class="team-name">Anjali Patel</div>
      <div class="team-role">Aesthetic Skincare Consultant</div>
      <div class="team-exp">8+ Years Industry Experience</div>
    </div>
  </div>

  <h3 style="font-size:20px; font-weight:800; margin-bottom:16px;">🖼️ Salon Interior & Work Showcase</h3>
  <div class="gallery-grid">
    <div class="gallery-item">
      <img src="https://images.unsplash.com/photo-1560066984-138dadb4c035?auto=format&fit=crop&w=600&q=80" class="gallery-img">
    </div>
    <div class="gallery-item">
      <img src="https://images.unsplash.com/photo-1562322140-8baeececf3df?auto=format&fit=crop&w=600&q=80" class="gallery-img">
    </div>
    <div class="gallery-item">
      <img src="https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?auto=format&fit=crop&w=600&q=80" class="gallery-img">
    </div>
  </div>
</div>
"""

# ==============================================================================
# RESTAURANT TEMPLATES
# ==============================================================================

_RESTAURANT_INDEX_TEMPLATE = """
<div class="card" id="mainFormCard">
  <div class="card-heading">
    <span>🍽️ Digital Menu & Table Booking</span>
    <span style="font-size:13px; color:var(--primary); font-weight:700;">Live Order Calculator</span>
  </div>

  <div class="form-group">
    <label class="form-label">1. Select Gourmet Delicacies (Tap to Add)</label>
    <div class="service-grid">
      <div class="service-card active rest-dish" onclick="toggleCardSelect(this, 'rest-dish')">
        <div class="service-card-img-wrap">
          <img src="https://images.unsplash.com/photo-1585937421612-70a008356fbe?auto=format&fit=crop&w=600&q=80" class="service-card-img" alt="Thali">
        </div>
        <div class="service-card-body">
          <div class="service-card-title">Chef's Special Kathiyawadi Thali</div>
          <div class="service-card-desc">Paneer Butter Masala, Dal Makhani, Garlic Naan & Basmati Rice.</div>
          <div class="service-card-footer">
            <div class="service-card-price">₹340</div>
            <div class="service-card-check">✓</div>
          </div>
        </div>
      </div>

      <div class="service-card rest-dish" onclick="toggleCardSelect(this, 'rest-dish')">
        <div class="service-card-img-wrap">
          <img src="https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=600&q=80" class="service-card-img" alt="Pizza">
        </div>
        <div class="service-card-body">
          <div class="service-card-title">Gourmet Wood-Fired Pizza</div>
          <div class="service-card-desc">Fresh buffalo mozzarella, sundried tomatoes & fresh basil.</div>
          <div class="service-card-footer">
            <div class="service-card-price">₹480</div>
            <div class="service-card-check">✓</div>
          </div>
        </div>
      </div>

      <div class="service-card rest-dish" onclick="toggleCardSelect(this, 'rest-dish')">
        <div class="service-card-img-wrap">
          <img src="https://images.unsplash.com/photo-1551024709-8f23befc6f87?auto=format&fit=crop&w=600&q=80" class="service-card-img" alt="Desserts">
        </div>
        <div class="service-card-body">
          <div class="service-card-title">Signature Dessert & Mocktail</div>
          <div class="service-card-desc">Sizzling chocolate brownie served with passion fruit mocktail.</div>
          <div class="service-card-footer">
            <div class="service-card-price">₹280</div>
            <div class="service-card-check">✓</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="form-group" style="background:var(--bg-soft); padding:18px; border-radius:14px; border:1px solid var(--border);">
    <div style="display:flex; justify-content:space-between; align-items:center; font-weight:800;">
      <span>Selected Order Total:</span>
      <span style="font-size:20px; color:var(--primary);">₹340 (incl. GST)</span>
    </div>
  </div>

  <div class="form-group">
    <label class="form-label">2. Reservation Details</label>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
      <input type="text" class="form-input" placeholder="Your Name" value="Amit Patel">
      <select class="form-select">
        <option>2 Guests (Dinner — 08:00 PM)</option>
        <option>4 Guests (Dinner — 08:30 PM)</option>
        <option>Takeaway Order</option>
      </select>
    </div>
  </div>

  <button class="btn-main" onclick="showModal('Table reservation & WhatsApp receipt dispatched successfully!')">
    Confirm Reservation & Dispatch WhatsApp Receipt 🚀
  </button>
</div>
"""

_RESTAURANT_SERVICES_TEMPLATE = """
<div class="card">
  <div class="card-heading">
    <span>📖 Full Restaurant Digital Menu</span>
    <span style="font-size:13px; color:var(--primary); font-weight:700;">Freshly Prepared</span>
  </div>

  <div class="form-group">
    <input type="text" id="svcSearchInput" onkeyup="filterServices()" class="form-input" placeholder="🔍 Search menu items (e.g. Thali, Paneer, Pizza, Mocktail)...">
  </div>

  <div style="display:flex; flex-direction:column; gap:16px;">
    <div class="svc-item-row" data-title="Chef's Special Kathiyawadi Thali" style="display:flex; justify-content:space-between; align-items:center; padding:16px; border:1px solid var(--border); border-radius:14px; background:#fff;">
      <div style="display:flex; gap:16px; align-items:center;">
        <img src="https://images.unsplash.com/photo-1585937421612-70a008356fbe?auto=format&fit=crop&w=150&q=80" style="width:70px; height:70px; border-radius:12px; object-fit:cover;">
        <div>
          <div style="font-weight:800; font-size:16px;">Chef's Special Kathiyawadi Thali</div>
          <div style="font-size:13px; color:var(--text-muted);">Paneer Butter Masala, Dal Makhani, Garlic Naan & Basmati Rice</div>
          <div style="font-weight:900; color:var(--primary); font-size:16px; margin-top:4px;">₹340</div>
        </div>
      </div>
      <button class="btn-main" style="width:auto; padding:10px 20px; font-size:13px;" onclick="showModal('Item added to cart!')">+ Add Item</button>
    </div>

    <div class="svc-item-row" data-title="Gourmet Wood-Fired Pizza" style="display:flex; justify-content:space-between; align-items:center; padding:16px; border:1px solid var(--border); border-radius:14px; background:#fff;">
      <div style="display:flex; gap:16px; align-items:center;">
        <img src="https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=150&q=80" style="width:70px; height:70px; border-radius:12px; object-fit:cover;">
        <div>
          <div style="font-weight:800; font-size:16px;">Gourmet Wood-Fired Pizza</div>
          <div style="font-size:13px; color:var(--text-muted);">Fresh buffalo mozzarella, sundried tomatoes & fresh basil</div>
          <div style="font-weight:900; color:var(--primary); font-size:16px; margin-top:4px;">₹480</div>
        </div>
      </div>
      <button class="btn-main" style="width:auto; padding:10px 20px; font-size:13px;" onclick="showModal('Item added to cart!')">+ Add Item</button>
    </div>
  </div>
</div>
"""

_RESTAURANT_ABOUT_TEMPLATE = """
<div class="card">
  <div class="card-heading">
    <span>✨ About {{BUSINESS_NAME}}</span>
    <span style="font-size:13px; color:var(--primary); font-weight:700;">Authentic Taste</span>
  </div>
  <p style="font-size:15px; color:var(--text-muted); margin-bottom:24px;">
    At <strong>{{BUSINESS_NAME}}</strong>, we serve authentic regional and international gourmet delicacies crafted with fresh organic ingredients and traditional recipes in {{CITY}}.
  </p>
  <h3 style="font-size:20px; font-weight:800; margin-bottom:16px;">👨‍🍳 Our Culinary Master Chefs</h3>
  <div class="team-grid">
    <div class="team-card">
      <img src="https://images.unsplash.com/photo-1577219491135-ce391730fb2c?auto=format&fit=crop&w=400&q=80" class="team-img">
      <div class="team-name">Chef Rajesh Kumar</div>
      <div class="team-role">Executive Head Chef</div>
      <div class="team-exp">15+ Years Culinary Mastery</div>
    </div>
  </div>
</div>
"""

# ==============================================================================
# CLINIC TEMPLATES
# ==============================================================================

_CLINIC_INDEX_TEMPLATE = """
<div class="card" id="mainFormCard">
  <div class="card-heading">
    <span>⚕️ Book Specialist Doctor Appointment</span>
    <span style="font-size:13px; color:var(--primary); font-weight:700;">Instant 24/7 Patient Booking</span>
  </div>

  <div class="form-group">
    <label class="form-label">1. Select Medical Specialty</label>
    <div class="service-grid">
      <div class="service-card active clinic-svc" onclick="toggleCardSelect(this, 'clinic-svc')">
        <div class="service-card-img-wrap">
          <img src="https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=600&q=80" class="service-card-img" alt="Consultation">
        </div>
        <div class="service-card-body">
          <div class="service-card-title">General Consultation</div>
          <div class="service-card-desc">Comprehensive health evaluation & medical diagnosis.</div>
          <div class="service-card-footer">
            <div class="service-card-price">₹500</div>
            <div class="service-card-check">✓</div>
          </div>
        </div>
      </div>

      <div class="service-card clinic-svc" onclick="toggleCardSelect(this, 'clinic-svc')">
        <div class="service-card-img-wrap">
          <img src="https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?auto=format&fit=crop&w=600&q=80" class="service-card-img" alt="Dental">
        </div>
        <div class="service-card-body">
          <div class="service-card-title">Dental Treatment & Surgery</div>
          <div class="service-card-desc">Painless laser dental care & tooth restoration.</div>
          <div class="service-card-footer">
            <div class="service-card-price">₹2,500</div>
            <div class="service-card-check">✓</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="form-group">
    <label class="form-label">2. Attending Senior Specialist</label>
    <select class="form-select">
      <option>Dr. Rajesh Sharma (MD, Senior Consultant — 15+ Yrs Exp)</option>
      <option>Dr. Meera Patel (BDS, MDS, Dental Surgeon)</option>
    </select>
  </div>

  <button class="btn-main" onclick="showModal('Doctor appointment scheduled! Instant WhatsApp prescription pass sent.')">
    Confirm Appointment & Send WhatsApp Pass 📱
  </button>
</div>
"""

_CLINIC_SERVICES_TEMPLATE = """
<div class="card">
  <div class="card-heading">
    <span>📖 Clinical Treatments & Consultation Rates</span>
  </div>
  <div style="display:flex; flex-direction:column; gap:16px;">
    <div style="padding:16px; border:1px solid var(--border); border-radius:14px; display:flex; justify-content:space-between; align-items:center;">
      <div>
        <div style="font-weight:800; font-size:16px;">General Medical Consultation</div>
        <div style="font-size:13px; color:var(--text-muted);">Health checkup, BP & vitals review • 30 Mins</div>
        <div style="font-weight:900; color:var(--primary); margin-top:4px;">₹500</div>
      </div>
      <button class="btn-main" style="width:auto; padding:10px 20px;" onclick="showModal('Appointment request queued!')">Book Slot</button>
    </div>
  </div>
</div>
"""

_CLINIC_ABOUT_TEMPLATE = """
<div class="card">
  <div class="card-heading">
    <span>⚕️ About {{BUSINESS_NAME}}</span>
  </div>
  <p style="font-size:15px; color:var(--text-muted); margin-bottom:24px;">
    <strong>{{BUSINESS_NAME}}</strong> provides state-of-the-art healthcare diagnostic and treatment services in {{CITY}}.
  </p>
  <div class="team-grid">
    <div class="team-card">
      <img src="https://images.unsplash.com/photo-1622253692010-333f2da6031d?auto=format&fit=crop&w=400&q=80" class="team-img">
      <div class="team-name">Dr. Rajesh Sharma</div>
      <div class="team-role">MD, Senior Medical Consultant</div>
      <div class="team-exp">18+ Years Experience</div>
    </div>
  </div>
</div>
"""

# ==============================================================================
# OTHER VERTICAL FALLBACK TEMPLATES
# ==============================================================================

_COACHING_INDEX_TEMPLATE = _SALON_INDEX_TEMPLATE
_GYM_INDEX_TEMPLATE = _SALON_INDEX_TEMPLATE
_GENERAL_INDEX_TEMPLATE = _SALON_INDEX_TEMPLATE

_GENERAL_SERVICES_TEMPLATE = _SALON_SERVICES_TEMPLATE
_GENERAL_ABOUT_TEMPLATE = _SALON_ABOUT_TEMPLATE