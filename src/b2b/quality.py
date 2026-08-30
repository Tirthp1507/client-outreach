"""Quality evaluation for b2b artifacts (outreach + demos).

A gatekeeper for the <em>content</em> layer: demos and outreach drafts must be
traceable to evidence, contain no placeholder/fabrication markers, include a
low-friction CTA, and hold up to a basic spam sniff. Scores 0-100; a report
below ``pass_threshold`` should not reach the human approval queue.
"""

from __future__ import annotations

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
    """Checks a generated demo renders and is not a placeholder shell."""

    def check(self, demo: DemoRecord, artifact_root: Optional[Path] = None) -> QualityReport:
        issues: List[str] = []
        score = 100.0
        path = Path(demo.artifact_path) if demo.artifact_path else None
        if artifact_root:
            path = artifact_root / path if path else None
        if demo.status != DemoStatus.READY:
            score -= 40
            issues.append(f"Demo status is not READY ({demo.status.value})")
        if path is None or not path.exists():
            score -= 50
            issues.append(f"Artifact file missing: {path}")
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            if len(text) < 2000:
                score -= 15
                issues.append("Suspiciously small HTML page")
            for marker in ("coming soon", "under construction", "lorem ipsum", "placeholder text"):
                if marker in text.lower():
                    score -= 20
                    issues.append(f"Placeholder marker in demo HTML: '{marker}'")
            for needle in ("<html", "<script", "<style"):
                if needle not in text.lower():
                    score -= 15
                    issues.append(f"Missing expected HTML element: {needle}")
        return QualityReport(score=max(0.0, round(score, 1)),
                             passed=score >= 70.0, issues=issues)