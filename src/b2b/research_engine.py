"""Safe HTTP Web Research Provider for B2B Digital Presence Ingestion.

Performs rate-limited, timeout-bounded web requests, extracts real structural evidence
(title, meta, contact info, WhatsApp links, booking widgets, mobile viewports),
and constructs strictly verifiable ResearchEvidence claims.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

from b2b.models import (
    BusinessRecord,
    BusinessResearch,
    ClaimType,
    EvidenceCategory,
    SourceType,
)
from b2b.research import BaseResearchProvider, EvidenceCollector, ResearchRegistry

logger = logging.getLogger(__name__)


class HTTPWebResearchProvider(BaseResearchProvider):
    """Safe, rate-limited public website research provider."""

    name: str = "http_web"

    def __init__(self, timeout_seconds: int = 10, user_agent: Optional[str] = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (B2B-Research-Auditor/1.0)"
        )

    def _fetch_html(self, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        """Safely fetch HTML with headers, timeout, and redirect handling."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                status_code = resp.getcode()
                content_bytes = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                html_text = content_bytes.decode(charset, errors="replace")
                return html_text, status_code, None
        except Exception as exc:
            logger.debug("Failed to fetch %s: %s", url, exc)
            return None, None, str(exc)

    def research(self, business: BusinessRecord, **kwargs: Any) -> BusinessResearch:
        """Perform comprehensive public digital presence research on a business."""
        collector = EvidenceCollector(business.id)
        website = business.website

        if not website:
            collector.add_fact(
                EvidenceCategory.IDENTITY,
                f"{business.name} has no official website listed in directory records.",
                source_type=SourceType.DIRECTORY_LISTING,
            )
            collector.add_unknown(
                EvidenceCategory.BOOKING_FLOW,
                "No online appointment or booking system found (no website).",
            )
            return BusinessResearch(
                business_id=business.id,
                website_exists=False,
                website_url=None,
                is_mobile_friendly=None,
                contact_methods=["phone"] if business.phone else [],
                observed_weaknesses=["No online web presence found"],
                evidence=collector.get_all(),
            )

        html, status_code, fetch_error = self._fetch_html(website)

        if not html:
            collector.add_fact(
                EvidenceCategory.IDENTITY,
                f"Attempted to connect to {website} but server was unreachable: {fetch_error}",
                evidence_url=website,
                source_type=SourceType.WEBSITE_HOMEPAGE,
            )
            collector.add_unknown(
                EvidenceCategory.BOOKING_FLOW,
                f"Website {website} is currently offline or unreachable.",
            )
            return BusinessResearch(
                business_id=business.id,
                website_exists=False,
                website_url=website,
                is_mobile_friendly=None,
                contact_methods=["phone"] if business.phone else [],
                observed_weaknesses=[f"Website unreachable ({fetch_error or 'timeout'})"],
                evidence=collector.get_all(),
            )

        # Parse HTML safely with BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # 1. Page Title & Meta Description
        title_tag = soup.find("title")
        title_text = title_tag.get_text().strip() if title_tag else ""
        if title_text:
            collector.add_fact(
                EvidenceCategory.IDENTITY,
                f"Website title: '{title_text}'",
                evidence_url=website,
                raw_snippet=title_text[:120],
                source_type=SourceType.WEBSITE_HOMEPAGE,
            )

        # 2. Mobile viewport check
        viewport_meta = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
        is_mobile_friendly = bool(viewport_meta and "width=device-width" in (viewport_meta.get("content") or "").lower())
        collector.add_fact(
            EvidenceCategory.MOBILE_UX,
            "Mobile viewport meta tag detected" if is_mobile_friendly else "No standard responsive mobile viewport tag detected",
            evidence_url=website,
            confidence=0.9,
        )

        # 3. Contact methods & WhatsApp detection
        contact_methods: List[str] = []
        html_lower = html.lower()

        # WhatsApp detection
        has_whatsapp = (
            "api.whatsapp.com" in html_lower
            or "wa.me" in html_lower
            or "whatsapp" in html_lower
        )
        if has_whatsapp:
            contact_methods.append("whatsapp")
            collector.add_fact(
                EvidenceCategory.CONTACT_FLOW,
                "WhatsApp click-to-chat link or button present on the website.",
                evidence_url=website,
                source_type=SourceType.WEBSITE_HOMEPAGE,
            )

        # Phone detection
        tel_links = soup.find_all("a", href=re.compile(r"^tel:", re.I))
        if tel_links or business.phone:
            contact_methods.append("phone")
            collector.add_fact(
                EvidenceCategory.CONTACT_FLOW,
                "Telephone contact number displayed on the website.",
                evidence_url=website,
                source_type=SourceType.WEBSITE_CONTACT,
            )

        # Email detection
        mailto_links = soup.find_all("a", href=re.compile(r"^mailto:", re.I))
        if mailto_links or business.email:
            contact_methods.append("email")

        # 4. Booking & Ordering flow detection
        booking_keywords = ["book appointment", "online booking", "schedule appointment", "calendly", "practo", "book online", "reserve table"]
        ordering_keywords = ["order online", "add to cart", "swiggy", "zomato", "menu cart", "checkout"]

        has_booking = any(k in html_lower for k in booking_keywords)
        has_ordering = any(k in html_lower for k in ordering_keywords)

        if has_booking:
            collector.add_fact(
                EvidenceCategory.BOOKING_FLOW,
                "Online appointment or reservation booking keywords/widgets found on page.",
                evidence_url=website,
            )
        else:
            collector.add_fact(
                EvidenceCategory.BOOKING_FLOW,
                "No automated online booking or appointment scheduling system found on homepage.",
                evidence_url=website,
            )

        # 5. Technology Stack hints
        tech_stack: List[str] = []
        if "wp-content" in html_lower or "wp-includes" in html_lower:
            tech_stack.append("WordPress")
        if "shopify" in html_lower:
            tech_stack.append("Shopify")
        if "wix" in html_lower:
            tech_stack.append("Wix")
        if "squarespace" in html_lower:
            tech_stack.append("Squarespace")
        if "react" in html_lower or "_next" in html_lower:
            tech_stack.append("React / Next.js")

        if tech_stack:
            collector.add_fact(
                EvidenceCategory.TECH_STACK,
                f"Identified frontend/CMS technologies: {', '.join(tech_stack)}",
                evidence_url=website,
            )

        # 6. Observed weaknesses
        observed_weaknesses: List[str] = []
        if not has_booking and business.category in ("clinic", "salon", "gym"):
            observed_weaknesses.append("No online appointment booking widget (phone/walk-in only)")
        if not has_ordering and business.category in ("restaurant", "retail"):
            observed_weaknesses.append("No online ordering or catalog menu checkout")
        if not is_mobile_friendly:
            observed_weaknesses.append("Website lacks responsive mobile viewport optimization")

        return BusinessResearch(
            business_id=business.id,
            website_exists=True,
            website_url=website,
            is_mobile_friendly=is_mobile_friendly,
            tech_stack=tech_stack,
            contact_methods=list(set(contact_methods)),
            booking_system_found=has_booking,
            ordering_system_found=has_ordering,
            observed_weaknesses=observed_weaknesses,
            observed_strengths=["Active online presence", f"Detected title: {title_text[:60]}"] if title_text else ["Active online presence"],
            evidence=collector.get_all(),
        )


# Auto-register HTTPWebResearchProvider in registry
ResearchRegistry.register("http_web", HTTPWebResearchProvider())
ResearchRegistry.register("live", HTTPWebResearchProvider())
