"""Quality evaluation for b2b artifacts (outreach + demos).

A gatekeeper for the <em>content</em> layer: demos and outreach drafts must be
traceable to evidence, contain no placeholder/fabrication markers, include a
low-friction CTA, and hold up to a basic spam sniff. Scores 0-100; a report
below ``pass_threshold`` should not reach the human approval queue.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import List, Optional

from b2b.models import DemoRecord, DemoStatus, OutreachRecord

logger = logging.getLogger(__name__)

PLACEHOLDER_MARKERS = ["{{", "}}", "TODO", "lorem ipsum", "coming soon", "under construction", "XXX"]
FABRICATION_MARKERS = ["password", "secret", "api_key", "credit card number", "12345678"]
CTA_HINTS = ["walkthrough", "call", "demo", "reply", "15-minute", "10 minutes", "short call"]
GENERIC_AGENTS = [
    "we build websites/apps. would you be interested",
    "generic template",
    "dear sir/madam",
]


@dataclass
class QualityReport:
    score: float
    passed: bool
    issues: List[str] = dc_field(default_factory=list)
    warnings: List[str] = dc_field(default_factory=list)

    def api_dict(self) -> dict:
        return {"score": self.score, "passed": self.passed,
                "issues": self.issues, "warnings": self.warnings}


class OutreachQualityChecker:
    """Scores an outreach draft on traceability, honesty, and structure."""

    def __init__(self, pass_threshold: float = 70.0) -> None:
        self.pass_threshold = pass_threshold

    def check(self, out: OutreachRecord, artifact_root: Optional[Path] = None) -> QualityReport:
        issues: List[str] = []
        warnings: List[str] = []
        score = 100.0

        def deduct(points: float, issue: str) -> None:
            nonlocal score
            score -= points
            issues.append(issue)

        subject = (out.subject or "").strip()
        body = (out.body_text or "").strip()

        if not subject:
            deduct(20, "Missing subject line")
        elif len(subject) > 140:
            deduct(5, f"Subject too long ({len(subject)} chars)")
        if len(body) < 250:
            deduct(20, f"Body suspiciously short ({len(body)} chars)")
        if not out.personalization_reasons:
            deduct(15, "No personalization_reasons recorded (untraceable personalization)")
        if not out.evidence_used:
            warnings.append("No evidence_used claims listed - soft-framing applicable but weaker")
            score -= 5
        if out.recipient_email and "@" not in out.recipient_email:
            deduct(10, f"Non-email recipient '{out.recipient_email}'")

        low = (subject + " " + body).lower()
        for marker in PLACEHOLDER_MARKERS:
            if marker == "XXX" and "xxx" not in low:
                continue
            if marker.lower() in low:
                deduct(25, f"Placeholder token detected: '{marker}'")
        for token in FABRICATION_MARKERS:
            if token in low:
                deduct(15, f"Fabrication marker detected: '{token}'")
        for phrase in GENERIC_AGENTS:
            if phrase in low:
                deduct(20, f"Generic/spammy phrasing detected: '{phrase}'")

        if not any(h in low for h in CTA_HINTS):
            warnings.append("No obvious low-friction CTA phrase detected")
            score -= 8

        try:
            body_low = low
            if out.evidence_used:
                tokens = {t for c in out.evidence_used if c for t in re.findall(r"[A-Za-z]{4,}", c.lower())}
                overlap = sum(1 for t in tokens if t in body_low)
                if tokens and overlap == 0:
                    warnings.append("Body does not reuse any terms from the evidence claims - verify grounding")
                    score -= 8
        except Exception:
            pass

        score = max(0.0, min(100.0, round(score, 1)))
        return QualityReport(score=score, passed=score >= self.pass_threshold,
                             issues=issues, warnings=warnings)


class DemoQualityChecker:
    """Comprehensive QA evaluation for generated commercial demo websites.
    
    Evaluates:
    - Responsive design & viewport configuration
    - Rich semantic HTML5 hierarchy
    - Curated high-res imagery & valid alt attributes
    - Front-end interactivity (forms, booking/cart scripts, modals)
    - Business personalization & contact integration
    - Mobile navigation & sticky action bars
    - Strict absence of placeholder / lorem ipsum content
    - Page completeness & styling density
    """

    def __init__(self, pass_threshold: float = 75.0) -> None:
        self.pass_threshold = pass_threshold

    def check(self, demo: DemoRecord, artifact_root: Optional[Path] = None) -> QualityReport:
        issues: List[str] = []
        warnings: List[str] = []
        score = 100.0

        path = Path(demo.artifact_path) if demo.artifact_path else None
        if artifact_root and path:
            path = artifact_root / path

        if demo.status != DemoStatus.READY:
            score -= 40.0
            issues.append(f"Demo status is not READY ({demo.status.value})")

        if path is None or not path.exists():
            score -= 50.0
            issues.append(f"Artifact file missing: {path}")
            return QualityReport(score=0.0, passed=False, issues=issues, warnings=warnings)

        text = path.read_text(encoding="utf-8", errors="replace")
        text_lower = text.lower()

        # 1. Content Density & Completeness
        if len(text) < 4000:
            score -= 20.0
            issues.append("Page content is suspiciously sparse (< 4KB)")
        elif len(text) < 8000:
            warnings.append("Page could include richer content and section depth")
            score -= 5.0

        # 2. Strict Anti-Placeholder Checks
        placeholder_markers = [
            "lorem ipsum", "dolor sit amet", "consectetur adipiscing",
            "placeholder text", "sample description", "coming soon",
            "under construction", "todo:", "dummy text", "your business name here",
        ]
        for marker in placeholder_markers:
            if marker in text_lower:
                score -= 15.0
                issues.append(f"Placeholder content detected: '{marker}'")

        # 3. Mobile Viewport & Meta Tags
        if "name=\"viewport\"" not in text_lower and "name='viewport'" not in text_lower:
            score -= 15.0
            issues.append("Missing responsive viewport meta tag")

        # 4. Semantic Structure
        for tag in ("<header", "<nav", "<main", "<section", "<footer"):
            if tag not in text_lower:
                score -= 6.0
                issues.append(f"Missing semantic HTML tag: {tag}")

        # 5. Heading Hierarchy
        h1_count = len(re.findall(r"<h1\b", text_lower))
        if h1_count == 0:
            score -= 10.0
            issues.append("Missing primary <h1> heading")
        elif h1_count > 2:
            warnings.append("Multiple <h1> headings detected; recommend exactly one per page")
            score -= 3.0

        if "<h2" not in text_lower or "<h3" not in text_lower:
            score -= 5.0
            warnings.append("Incomplete heading hierarchy (missing <h2> or <h3>)")

        # 6. Imagery Validation
        img_matches = re.findall(r"<img\s+([^>]+)>", text, re.IGNORECASE)
        if len(img_matches) < 3:
            score -= 15.0
            issues.append(f"Insufficient visual imagery: found {len(img_matches)} images (minimum 3 required)")
        else:
            missing_alt = 0
            for img_attrs in img_matches:
                if "alt=" not in img_attrs.lower():
                    missing_alt += 1
            if missing_alt > 0:
                warnings.append(f"{missing_alt} image(s) missing descriptive alt attributes")
                score -= 3.0

        # 7. Front-End Interactivity & Dynamic Scripts
        if "<script" not in text_lower:
            score -= 15.0
            issues.append("Missing interactive JavaScript runtime")
        else:
            interactive_signals = ["onclick=", "onsubmit=", "addeventlistener", "showtoast", "openmodal", "cart", "booking"]
            found_signals = sum(1 for s in interactive_signals if s in text_lower)
            if found_signals < 2:
                score -= 10.0
                issues.append("Low front-end interactivity: lacks dynamic event handlers or action modals")

        # 8. Mobile Navigation & Floating Actions
        if "mobile-menu" not in text_lower and "mobiletoggle" not in text_lower and "hamburger" not in text_lower:
            score -= 8.0
            warnings.append("No mobile hamburger navigation detected")

        if "mobile-sticky" not in text_lower and "whatsapp" not in text_lower:
            score -= 6.0
            warnings.append("Missing mobile quick-action bar or WhatsApp trigger")

        # 9. Business Personalization
        if demo.metadata_json:
            meta = demo.metadata_json
            biz_name = meta.get("business_name")
            if biz_name:
                biz_low = biz_name.lower()
                biz_escaped = html.escape(biz_low)
                if biz_low not in text_lower and biz_escaped not in text_lower:
                    score -= 15.0
                    issues.append(f"Business name '{biz_name}' not found in rendered demo")

            city = meta.get("city")
            if city and city.lower() not in text_lower:
                score -= 5.0
                warnings.append(f"Location '{city}' not mentioned in demo copy")

        score = max(0.0, min(100.0, round(score, 1)))
        return QualityReport(
            score=score,
            passed=score >= self.pass_threshold and len(issues) == 0,
            issues=issues,
            warnings=warnings,
        )