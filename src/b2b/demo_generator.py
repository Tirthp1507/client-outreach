"""Demo Strategy & Generator: Build client-specific, deeply interactive, vertical-tailored HTML prototypes.

Every generated prototype is fully self-contained (zero external network dependencies), mobile-first responsive,
and genuinely custom to the business's identity, identified operational problem, and proposed solution.
Features ultra-attractive modern UI aesthetics with Google Fonts (Outfit & Inter), glassmorphism cards,
smooth CSS gradients, micro-animations, and dynamic real-time interaction logic.
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
        short_title = f"{business.name} — Interactive Solution Prototype"

        return DemoBlueprint(
            business_id=business.id,
            opportunity_id=opp.id,
            vertical=vertical,
            demo_type=demo_type,
            title=short_title,
            problem=opp.problem_summary or "Manual inquiry flow without instant online booking or ordering.",
            solution=opp.proposed_solution or "Modern, mobile-first interactive booking & inquiry web app.",
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
    """Generates fully self-contained, responsive, client-specific HTML prototypes."""

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

    def _render(self, business: BusinessRecord, bp: DemoBlueprint) -> str:
        theme = _VERTICAL_THEMES.get(bp.vertical, _VERTICAL_THEMES[VerticalType.GENERAL_SMB])
        content_html = self._generate_vertical_content(business, bp, theme)

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
# HTML TEMPLATES & VERTICAL SECTIONS
# ==============================================================================

_MASTER_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{TITLE}}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap" rel="stylesheet">
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
      --shadow-md: 0 10px 30px -10px rgba(15, 23, 42, 0.08);
      --radius-lg: 20px;
      --radius-md: 12px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      background: #f8fafc;
      color: var(--text);
      line-height: 1.6;
      padding-bottom: 80px;
      -webkit-font-smoothing: antialiased;
    }
    h1, h2, h3, h4, .brand-title {
      font-family: 'Outfit', sans-serif;
    }
    /* Demo Header Banner */
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
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
    .proto-status {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-weight: 500;
      color: #94a3b8;
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
    .wrapper {
      max-width: 900px;
      margin: 0 auto;
      padding: 24px 16px;
    }
    /* Hero Business Identity Card */
    .biz-header {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 28px;
      margin-bottom: 24px;
      box-shadow: var(--shadow-md);
      position: relative;
      overflow: hidden;
    }
    .biz-header::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 6px;
      background: var(--gradient);
    }
    .biz-title-row {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      flex-wrap: wrap;
    }
    .biz-name {
      font-size: 28px;
      font-weight: 800;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .biz-icon {
      font-size: 32px;
      background: var(--bg-soft);
      width: 52px;
      height: 52px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 14px;
      border: 1px solid var(--border);
    }
    .biz-meta {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-top: 8px;
      flex-wrap: wrap;
    }
    .biz-tag {
      background: var(--badge-bg);
      color: var(--badge-text);
      font-size: 12px;
      font-weight: 700;
      padding: 4px 12px;
      border-radius: 20px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .biz-location {
      font-size: 13px;
      color: var(--text-muted);
      font-weight: 500;
    }
    /* Solution Callout Box */
    .solution-box {
      margin-top: 20px;
      padding: 16px 20px;
      background: var(--bg-soft);
      border-left: 4px solid var(--primary);
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.5;
    }
    .solution-box strong { color: var(--primary-dark); font-weight: 700; }

    /* Interactive Cards */
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 28px;
      margin-bottom: 24px;
      box-shadow: var(--shadow-md);
      transition: transform 0.2s, box-shadow 0.2s;
    }
    .card-heading {
      font-size: 20px;
      font-weight: 800;
      color: var(--text);
      margin-bottom: 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .form-group {
      margin-bottom: 18px;
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
      padding: 12px 16px;
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      font-size: 15px;
      font-family: inherit;
      background: #fff;
      color: var(--text);
      transition: all 0.15s;
    }
    .form-input:focus, .form-select:focus, .form-textarea:focus {
      outline: none;
      border-color: var(--primary);
      box-shadow: 0 0 0 4px rgba(2, 132, 199, 0.15);
    }
    .btn-main {
      background: var(--gradient);
      color: #fff;
      border: none;
      padding: 14px 28px;
      border-radius: var(--radius-md);
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
      width: 100%;
      transition: all 0.2s;
      box-shadow: 0 4px 14px rgba(2, 132, 199, 0.3);
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }
    .btn-main:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(2, 132, 199, 0.4);
    }
    .btn-main:active {
      transform: translateY(0);
    }

    /* Selection Grids */
    .select-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 14px;
      margin-bottom: 20px;
    }
    .select-item {
      border: 2px solid var(--border);
      border-radius: var(--radius-md);
      padding: 16px;
      cursor: pointer;
      background: #fff;
      transition: all 0.2s ease;
      user-select: none;
      position: relative;
    }
    .select-item:hover {
      border-color: var(--primary);
      transform: translateY(-2px);
      box-shadow: var(--shadow-sm);
    }
    .select-item.active {
      border-color: var(--primary);
      background: var(--bg-soft);
      box-shadow: 0 0 0 1px var(--primary);
    }
    .select-item-title {
      font-weight: 700;
      font-size: 15px;
      color: var(--text);
      margin-bottom: 4px;
    }
    .select-item-sub {
      font-size: 13px;
      color: var(--text-muted);
    }
    .select-item-price {
      font-size: 14px;
      font-weight: 800;
      color: var(--primary);
      margin-top: 8px;
    }

    /* Slot Chips */
    .chip-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 20px;
    }
    .chip {
      padding: 10px 18px;
      border: 1px solid var(--border);
      border-radius: 30px;
      background: #fff;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s;
    }
    .chip:hover { border-color: var(--primary); color: var(--primary); }
    .chip.active {
      background: var(--primary);
      color: #fff;
      border-color: var(--primary);
      box-shadow: 0 2px 8px rgba(2, 132, 199, 0.3);
    }

    /* Modal Overlay */
    .modal-backdrop {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.7);
      backdrop-filter: blur(6px);
      z-index: 999;
      align-items: center;
      justify-content: center;
      padding: 16px;
    }
    .modal-backdrop.show { display: flex; }
    .modal-card {
      background: #fff;
      border-radius: var(--radius-lg);
      max-width: 480px;
      width: 100%;
      padding: 32px;
      box-shadow: 0 20px 50px rgba(0,0,0,0.25);
      text-align: center;
      animation: modalPop 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    @keyframes modalPop {
      0% { transform: scale(0.9); opacity: 0; }
      100% { transform: scale(1); opacity: 1; }
    }
    .modal-icon {
      font-size: 48px;
      margin-bottom: 16px;
      display: inline-block;
    }
    .modal-title {
      font-size: 22px;
      font-weight: 800;
      color: var(--text);
      margin-bottom: 8px;
    }
    .modal-body {
      font-size: 14px;
      color: var(--text-muted);
      margin-bottom: 24px;
      line-height: 1.6;
    }
    .modal-wa-box {
      background: #f0fdf4;
      border: 1px solid #bbf7d0;
      color: #166534;
      padding: 12px 16px;
      border-radius: 12px;
      font-size: 13px;
      margin-bottom: 20px;
      text-align: left;
    }

    /* Sticky Footer Bar */
    .sticky-bar {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(10px);
      border-top: 1px solid var(--border);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      z-index: 900;
    }
    .sticky-info {
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
    }

    @media (max-width: 640px) {
      .wrapper { padding: 16px 12px; }
      .biz-header, .card { padding: 20px 16px; }
      .biz-name { font-size: 22px; }
      .select-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>

  <!-- Top Prototype Info Bar -->
  <div class="prototype-bar">
    <div style="display:flex; align-items:center; gap:8px;">
      <span class="proto-badge">CUSTOM DEMO PROTOTYPE</span>
      <span style="font-weight:600;">Tailored for {{BUSINESS_NAME}}</span>
    </div>
    <div class="proto-status">
      <span class="pulse-dot"></span>
      <span>Simulated Client Experience — Zero Server Transmission</span>
    </div>
  </div>

  <div class="wrapper">
    <!-- Business Identity Hero Card -->
    <div class="biz-header">
      <div class="biz-title-row">
        <div>
          <div class="biz-name">
            <span class="biz-icon">{{ICON}}</span>
            <span>{{BUSINESS_NAME}}</span>
          </div>
          <div class="biz-meta">
            <span class="biz-tag">✓ {{CATEGORY}}</span>
            <span class="biz-location">📍 {{CITY}} • {{ADDRESS}}</span>
          </div>
        </div>
      </div>

      <div class="solution-box">
        <strong>Proposed Digital Solution:</strong> {{SOLUTION}}
      </div>
    </div>

    <!-- Vertical Specific Interactive Prototype Content -->
    {{CONTENT_HTML}}

  </div>

  <!-- Interactive WhatsApp Confirmation Modal -->
  <div class="modal-backdrop" id="confirmationModal">
    <div class="modal-card">
      <div class="modal-icon">✅</div>
      <div class="modal-title">Booking Request Sent!</div>
      <div class="modal-body" id="modalBodyText">
        Your booking request has been simulated successfully. In production, this instantly updates your schedule and notifies the client.
      </div>
      <div class="modal-wa-box">
        <strong>📱 Simulated WhatsApp Alert:</strong><br>
        "Hi! Your appointment at {{BUSINESS_NAME}} is reserved. We look forward to welcoming you!"
      </div>
      <button class="btn-main" onclick="closeModal()">Got it & Close</button>
    </div>
  </div>

  <!-- Sticky Bottom Contact Bar -->
  <div class="sticky-bar">
    <div class="sticky-info">
      ⚡ Live Demonstration for {{BUSINESS_NAME}} ({{CITY}})
    </div>
    <button class="btn-main" style="width:auto; padding:10px 20px; font-size:13px;" onclick="scrollToAppt()">
      Try Booking Flow 🚀
    </button>
  </div>

  <script>
    function toggleSelect(el, groupClass) {
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

    function scrollToAppt() {
      const el = document.getElementById('mainFormCard');
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    }
  </script>
</body>
</html>
"""

# ==============================================================================
# VERTICAL SPECIFIC TEMPLATES
# ==============================================================================

_CLINIC_TEMPLATE = """
<div class="card" id="mainFormCard">
  <div class="card-heading">
    <span>⚕️ Book Doctor Appointment</span>
    <span style="font-size:12px; color:var(--primary); font-weight:600;">Instant 24/7 Booking</span>
  </div>

  <div class="form-group">
    <label class="form-label">1. Select Required Treatment / Service</label>
    <div class="select-grid">
      <div class="select-item active clinic-svc" onclick="toggleSelect(this, 'clinic-svc')">
        <div class="select-item-title">General Consultation</div>
        <div class="select-item-sub">Comprehensive checkup & diagnosis</div>
        <div class="select-item-price">₹500</div>
      </div>
      <div class="select-item clinic-svc" onclick="toggleSelect(this, 'clinic-svc')">
        <div class="select-item-title">Dental Implants / Root Canal</div>
        <div class="select-item-sub">Specialist procedural treatment</div>
        <div class="select-item-price">₹3,500+</div>
      </div>
      <div class="select-item clinic-svc" onclick="toggleSelect(this, 'clinic-svc')">
        <div class="select-item-title">Teeth Whitening / Aesthetic</div>
        <div class="select-item-sub">Laser whitening session</div>
        <div class="select-item-price">₹2,000</div>
      </div>
    </div>
  </div>

  <div class="form-group">
    <label class="form-label">2. Preferred Specialist Doctor</label>
    <select class="form-select" id="doctorSelect">
      <option>Dr. Sharma (Senior Consultant — 15+ Yrs Exp)</option>
      <option>Dr. Patel (Dental & Oral Surgeon)</option>
      <option>Dr. Verma (Cosmetic Specialist)</option>
    </select>
  </div>

  <div class="form-group">
    <label class="form-label">3. Select Appointment Slot</label>
    <div class="chip-grid">
      <div class="chip active slot-chip" onclick="toggleChip(this, 'slot-chip')">Today 10:30 AM</div>
      <div class="chip slot-chip" onclick="toggleChip(this, 'slot-chip')">Today 04:00 PM</div>
      <div class="chip slot-chip" onclick="toggleChip(this, 'slot-chip')">Tomorrow 11:00 AM</div>
      <div class="chip slot-chip" onclick="toggleChip(this, 'slot-chip')">Tomorrow 06:30 PM</div>
    </div>
  </div>

  <div class="form-group">
    <label class="form-label">4. Patient Contact Details</label>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
      <input type="text" class="form-input" placeholder="Full Name" value="Rahul Sharma">
      <input type="tel" class="form-input" placeholder="Mobile Number" value="{{PHONE}}">
    </div>
  </div>

  <button class="btn-main" onclick="showModal('Appointment successfully scheduled! A WhatsApp confirmation link has been simulated for your patient.')">
    Confirm Appointment & Receive WhatsApp Alert 📱
  </button>
</div>
"""

_RESTAURANT_TEMPLATE = """
<div class="card" id="mainFormCard">
  <div class="card-heading">
    <span>🍽️ Digital Menu & Table Reservation</span>
    <span style="font-size:12px; color:var(--primary); font-weight:600;">Live Ordering Prototype</span>
  </div>

  <div class="form-group">
    <label class="form-label">Featured Specialities (Tap + to add)</label>
    <div style="display:flex; flex-direction:column; gap:12px;">
      <div style="display:flex; justify-content:space-between; align-items:center; padding:12px; border:1px solid var(--border); border-radius:12px;">
        <div>
          <div style="font-weight:700;">Chef's Special Thali / Main Course</div>
          <div style="font-size:13px; color:var(--text-muted);">Paneer Butter Masala, Dal Makhani, Naan & Rice</div>
          <div style="font-weight:800; color:var(--primary); margin-top:4px;">₹320</div>
        </div>
        <button class="btn-main" style="width:auto; padding:6px 16px;" onclick="addCart(320)">+ Add</button>
      </div>

      <div style="display:flex; justify-content:space-between; align-items:center; padding:12px; border:1px solid var(--border); border-radius:12px;">
        <div>
          <div style="font-weight:700;">Wood-Fired Gourmet Pizza / Starters</div>
          <div style="font-size:13px; color:var(--text-muted);">Fresh Mozzarella, Basil, Olive Oil</div>
          <div style="font-weight:800; color:var(--primary); margin-top:4px;">₹450</div>
        </div>
        <button class="btn-main" style="width:auto; padding:6px 16px;" onclick="addCart(450)">+ Add</button>
      </div>
    </div>
  </div>

  <div class="form-group" style="background:var(--bg-soft); padding:16px; border-radius:12px;">
    <div style="display:flex; justify-content:space-between; align-items:center; font-weight:700;">
      <span>Live Order Summary:</span>
      <span id="cartTotal" style="font-size:18px; color:var(--primary);">Total: ₹0</span>
    </div>
  </div>

  <div class="form-group">
    <label class="form-label">Table Reservation or Takeaway</label>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
      <input type="text" class="form-input" placeholder="Your Name" value="Amit Patel">
      <select class="form-select">
        <option>2 Guests (Dinner - 8:00 PM)</option>
        <option>4 Guests (Dinner - 8:30 PM)</option>
        <option>Takeaway Order</option>
      </select>
    </div>
  </div>

  <button class="btn-main" onclick="showModal('Table reservation & order request received! Instant WhatsApp receipt simulated.')">
    Place Table Order via WhatsApp 🚀
  </button>
</div>

<script>
  let total = 0;
  function addCart(amt) {
    total += amt;
    document.getElementById('cartTotal').innerText = 'Total: ₹' + total + ' (incl. GST)';
  }
</script>
"""

_SALON_TEMPLATE = """
<div class="card" id="mainFormCard">
  <div class="card-heading">
    <span>✂️ Instant Salon & Spa Booking</span>
    <span style="font-size:12px; color:var(--primary); font-weight:600;">Stylist Schedule</span>
  </div>

  <div class="form-group">
    <label class="form-label">1. Choose Service Package</label>
    <div class="select-grid">
      <div class="select-item active salon-svc" onclick="toggleSelect(this, 'salon-svc')">
        <div class="select-item-title">Hair Styling & Care</div>
        <div class="select-item-sub">Haircut, Wash & Blow Dry</div>
        <div class="select-item-price">₹799</div>
      </div>
      <div class="select-item salon-svc" onclick="toggleSelect(this, 'salon-svc')">
        <div class="select-item-title">Luxury Facial & Spa</div>
        <div class="select-item-sub">Radiance cleanup & massage</div>
        <div class="select-item-price">₹1,499</div>
      </div>
      <div class="select-item salon-svc" onclick="toggleSelect(this, 'salon-svc')">
        <div class="select-item-title">Bridal / Premium Grooming</div>
        <div class="select-item-sub">Complete makeover package</div>
        <div class="select-item-price">₹3,999</div>
      </div>
    </div>
  </div>

  <div class="form-group">
    <label class="form-label">2. Select Preferred Stylist</label>
    <select class="form-select">
      <option>Any Available Top Stylist</option>
      <option>Priya (Master Hair Specialist)</option>
      <option>Karan (Beard & Hair Artist)</option>
    </select>
  </div>

  <div class="form-group">
    <label class="form-label">3. Select Time Slot</label>
    <div class="chip-grid">
      <div class="chip active salon-slot" onclick="toggleChip(this, 'salon-slot')">11:00 AM</div>
      <div class="chip salon-slot" onclick="toggleChip(this, 'salon-slot')">02:30 PM</div>
      <div class="chip salon-slot" onclick="toggleChip(this, 'salon-slot')">05:00 PM</div>
      <div class="chip salon-slot" onclick="toggleChip(this, 'salon-slot')">07:30 PM</div>
    </div>
  </div>

  <button class="btn-main" onclick="showModal('Salon appointment confirmed! Stylist calendar updated and client SMS notification sent.')">
    Confirm Salon Slot & Send SMS Reminder 📱
  </button>
</div>
"""

_COACHING_TEMPLATE = """
<div class="card" id="mainFormCard">
  <div class="card-heading">
    <span>🎓 Book Free Demo Class & Counseling</span>
    <span style="font-size:12px; color:var(--primary); font-weight:600;">Admissions Open</span>
  </div>

  <div class="form-group">
    <label class="form-label">1. Select Target Course / Standard</label>
    <div class="select-grid">
      <div class="select-item active coach-crs" onclick="toggleSelect(this, 'coach-crs')">
        <div class="select-item-title">Class 11th & 12th Board Prep</div>
        <div class="select-item-sub">Physics, Chemistry, Maths, Bio</div>
      </div>
      <div class="select-item coach-crs" onclick="toggleSelect(this, 'coach-crs')">
        <div class="select-item-title">IIT-JEE / NEET Intensive</div>
        <div class="select-item-sub">Target entrance coaching</div>
      </div>
      <div class="select-item coach-crs" onclick="toggleSelect(this, 'coach-crs')">
        <div class="select-item-title">Foundation (Class 8th–10th)</div>
        <div class="select-item-sub">Olympiad & NTSE focus</div>
      </div>
    </div>
  </div>

  <div class="form-group">
    <label class="form-label">2. Student & Parent Contact Information</label>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
      <input type="text" class="form-input" placeholder="Student Name" value="Aniket Verma">
      <input type="tel" class="form-input" placeholder="Parent Contact No." value="{{PHONE}}">
    </div>
  </div>

  <button class="btn-main" onclick="showModal('Free Demo Class seat reserved! Syllabus PDF link sent to WhatsApp.')">
    Reserve Free Demo Class Seat 🚀
  </button>
</div>
"""

_GYM_TEMPLATE = """
<div class="card" id="mainFormCard">
  <div class="card-heading">
    <span>🏋️‍♂️ 1-Day VIP Trial Pass & Membership</span>
    <span style="font-size:12px; color:var(--primary); font-weight:600;">Instant QR Pass</span>
  </div>

  <div class="form-group">
    <label class="form-label">1. Choose Membership Plan</label>
    <div class="select-grid">
      <div class="select-item active gym-plan" onclick="toggleSelect(this, 'gym-plan')">
        <div class="select-item-title">1-Day Free VIP Pass</div>
        <div class="select-item-sub">Full workout & sauna access</div>
        <div class="select-item-price">FREE</div>
      </div>
      <div class="select-item gym-plan" onclick="toggleSelect(this, 'gym-plan')">
        <div class="select-item-title">Quarterly Fitness Pass</div>
        <div class="select-item-sub">Gym + Personal Trainer</div>
        <div class="select-item-price">₹4,999</div>
      </div>
      <div class="select-item gym-plan" onclick="toggleSelect(this, 'gym-plan')">
        <div class="select-item-title">Annual All-Access VIP</div>
        <div class="select-item-sub">Unlimited classes & nutrition</div>
        <div class="select-item-price">₹14,999</div>
      </div>
    </div>
  </div>

  <div class="form-group">
    <label class="form-label">2. Member Details</label>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
      <input type="text" class="form-input" placeholder="Full Name" value="Vikas Mehta">
      <input type="tel" class="form-input" placeholder="WhatsApp Number" value="{{PHONE}}">
    </div>
  </div>

  <button class="btn-main" onclick="showModal('VIP Gym Pass generated! Instant QR pass sent to your WhatsApp number.')">
    Generate Free VIP Workout Pass 🎟️
  </button>
</div>
"""

_RETAIL_TEMPLATE = """
<div class="card" id="mainFormCard">
  <div class="card-heading">
    <span>🛍️ Store Product Catalog & WhatsApp Ordering</span>
    <span style="font-size:12px; color:var(--primary); font-weight:600;">Direct Store Order</span>
  </div>

  <div class="form-group">
    <label class="form-label">Featured Products Catalog</label>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
      <div style="padding:14px; border:1px solid var(--border); border-radius:12px;">
        <div style="font-weight:700;">Premium Product Pack A</div>
        <div style="font-size:13px; color:var(--text-muted);">In-stock item • Fast Delivery</div>
        <div style="font-weight:800; color:var(--primary); margin-top:6px;">₹1,250</div>
      </div>
      <div style="padding:14px; border:1px solid var(--border); border-radius:12px;">
        <div style="font-weight:700;">Special Combo Pack B</div>
        <div style="font-size:13px; color:var(--text-muted);">Trending bestseller</div>
        <div style="font-weight:800; color:var(--primary); margin-top:6px;">₹2,400</div>
      </div>
    </div>
  </div>

  <div class="form-group">
    <label class="form-label">Delivery Address & Phone</label>
    <input type="text" class="form-input" placeholder="Delivery Address" value="B-402, Green Acres, {{CITY}}">
  </div>

  <button class="btn-main" onclick="showModal('Order request formatted for WhatsApp dispatch!')">
    Dispatch Order to WhatsApp Shop 📱
  </button>
</div>
"""

_REAL_ESTATE_TEMPLATE = """
<div class="card" id="mainFormCard">
  <div class="card-heading">
    <span>🏢 Schedule VIP Site Visit & EMI Calculator</span>
    <span style="font-size:12px; color:var(--primary); font-weight:600;">Luxury Residences</span>
  </div>

  <div class="form-group">
    <label class="form-label">1. Preferred Unit Configuration</label>
    <div class="select-grid">
      <div class="select-item active re-unit" onclick="toggleSelect(this, 're-unit')">
        <div class="select-item-title">2 BHK Premium Residence</div>
        <div class="select-item-sub">1250 sq.ft • Balcony Deck</div>
        <div class="select-item-price">₹75 Lakhs+</div>
      </div>
      <div class="select-item re-unit" onclick="toggleSelect(this, 're-unit')">
        <div class="select-item-title">3 BHK Luxury Apartment</div>
        <div class="select-item-sub">1750 sq.ft • Clubhouse View</div>
        <div class="select-item-price">₹1.15 Cr+</div>
      </div>
    </div>
  </div>

  <div class="form-group">
    <label class="form-label">2. Visitor Information</label>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
      <input type="text" class="form-input" placeholder="Your Name" value="Sanjay Patel">
      <input type="tel" class="form-input" placeholder="Mobile Number" value="{{PHONE}}">
    </div>
  </div>

  <button class="btn-main" onclick="showModal('VIP Site visit scheduled! Cab pickup details & digital brochure sent.')">
    Book VIP Site Visit & Download Brochure 📄
  </button>
</div>
"""

_GENERAL_SMB_TEMPLATE = """
<div class="card" id="mainFormCard">
  <div class="card-heading">
    <span>⚡ Instant Service Quotation & Callback</span>
    <span style="font-size:12px; color:var(--primary); font-weight:600;">Direct Contact</span>
  </div>

  <div class="form-group">
    <label class="form-label">1. Select Desired Service</label>
    <div class="select-grid">
      <div class="select-item active smb-svc" onclick="toggleSelect(this, 'smb-svc')">
        <div class="select-item-title">Standard Service Consultation</div>
        <div class="select-item-sub">Professional evaluation & quote</div>
      </div>
      <div class="select-item smb-svc" onclick="toggleSelect(this, 'smb-svc')">
        <div class="select-item-title">Premium Complete Solution</div>
        <div class="select-item-sub">End-to-end execution</div>
      </div>
    </div>
  </div>

  <div class="form-group">
    <label class="form-label">2. Contact Details</label>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
      <input type="text" class="form-input" placeholder="Your Name / Business" value="Lead Contact">
      <input type="tel" class="form-input" placeholder="Phone Number" value="{{PHONE}}">
    </div>
  </div>

  <button class="btn-main" onclick="showModal('Service quote request sent! Priority callback scheduled within 15 mins.')">
    Request Priority Callback 📞
  </button>
</div>
"""