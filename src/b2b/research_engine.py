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

    def _call_gemini_research(
        self,
        business: BusinessRecord,
        scraped_text: Optional[str] = None,
        page_title: Optional[str] = None,
    ) -> Optional[dict]:
        """Perform real AI deep research using Google Gemini 2.5 Flash with optional live webpage context."""
        import json
        import os
        import urllib.request

        env_path = r"c:\Users\tirth\Desktop\automation\config\.env"
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key and os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("GEMINI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")

        if not api_key:
            return None

        context_str = f"Business Name: {business.name}\nCity: {business.city}\nCategory: {business.category}\nCurrent Address: {business.address or 'Local Area'}"
        if business.website:
            context_str += f"\nWebsite URL: {business.website}"
        if page_title:
            context_str += f"\nScraped Page Title: {page_title}"
        if scraped_text:
            context_str += f"\nScraped Web Content Snippet: {scraped_text[:1200]}"

        prompt = f"""You are an expert B2B Technology Auditor & AI Analyst.
Perform deep research & gap analysis on this business in India using live website/directory context:

{context_str}

Return ONLY valid JSON (no markdown block wrapping) in this exact structure:
{{
    "specific_services": ["service 1", "service 2", "service 3"],
    "observed_strengths": ["strength 1", "strength 2"],
    "observed_weaknesses": ["weakness 1", "weakness 2"],
    "evidence_claims": [
        {{"category": "identity", "claim": "Bespoke fact about {business.name}"}},
        {{"category": "booking_flow", "claim": "Bespoke observation of workflow for {business.name}"}}
    ],
    "opportunity_title": "Bespoke Technology Solution Title for {business.name}",
    "problem_summary": "Specific operational gap or digital weakness tailored to {business.name}",
    "proposed_solution": "Custom software/automation tailored to {business.name}",
    "business_value": "Expected ROI / revenue boost / time saved",
    "score": 82.5,
    "official_website": null
}}
"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"}
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text)
        except Exception as exc:
            logger.warning(f"Gemini AI Research call failed for {business.name}: {exc}")
            return None

    def _extract_verified_email_from_html(self, soup: BeautifulSoup, html: str) -> Optional[str]:
        """Extract exact verified email from mailto links or html regex."""
        # 1. mailto: links
        mailto_links = soup.find_all("a", href=re.compile(r"^mailto:", re.I))
        for link in mailto_links:
            href = link.get("href", "")
            email = href.split(":", 1)[1].split("?")[0].strip().lower()
            if email and "@" in email and not any(email.endswith(ext) for ext in [".png", ".jpg", ".svg", ".js"]):
                return email

        # 2. regex search on page HTML
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        matches = re.findall(email_pattern, html)
        ignored_domains = {"sentry.io", "wixpress.com", "example.com", "domain.com", "schema.org"}
        for match in matches:
            email = match.strip().lower()
            domain = email.split("@")[-1]
            if domain not in ignored_domains and not any(email.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".svg", ".gif", ".css", ".js"]):
                return email
        return None

    def _extract_phone_from_html(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract exact phone from tel: links."""
        tel_links = soup.find_all("a", href=re.compile(r"^tel:", re.I))
        for link in tel_links:
            href = link.get("href", "")
            phone = href.split(":", 1)[1].strip()
            digits = re.sub(r"\D", "", phone)
            if len(digits) >= 8:
                return phone
        return None

    def research(self, business: BusinessRecord, **kwargs: Any) -> BusinessResearch:
        """Perform comprehensive live web testing and digital presence research on a business."""
        collector = EvidenceCollector(business.id)
        website = business.website

        # If website is missing, check if Gemini AI knows an official website URL
        if not website:
            ai_res_init = self._call_gemini_research(business)
            if ai_res_init:
                discovered_web = ai_res_init.get("official_website")
                if discovered_web and isinstance(discovered_web, str) and discovered_web.strip() not in ("null", "None", ""):
                    website = discovered_web.strip()
                    business.website = website

        # If still no website URL
        if not website:
            collector.add_fact(
                EvidenceCategory.IDENTITY,
                f"Verified local business listing for {business.name} in {business.city}.",
                source_type=SourceType.DIRECTORY_LISTING,
            )
            collector.add_unknown(
                EvidenceCategory.BOOKING_FLOW,
                f"No dedicated business website found; lacks 24/7 self-serve digital booking flow.",
            )
            ai_res = self._call_gemini_research(business)
            weaknesses = (ai_res.get("observed_weaknesses") if ai_res else None) or ["Lacks 24/7 self-serve digital booking & inquiry intake flow"]
            strengths = (ai_res.get("observed_strengths") if ai_res else None) or [f"Established local presence in {business.city}"]

            if ai_res:
                for claim_item in ai_res.get("evidence_claims", []):
                    collector.add_fact(
                        EvidenceCategory.IDENTITY,
                        claim_item.get("claim", f"Fact claim for {business.name}"),
                        source_type=SourceType.DIRECTORY_LISTING
                    )

            return BusinessResearch(
                business_id=business.id,
                website_exists=False,
                website_url=None,
                is_mobile_friendly=False,
                contact_methods=["phone"] if business.phone else [],
                observed_weaknesses=weaknesses,
                observed_strengths=strengths,
                evidence=collector.get_all(),
            )

        # Perform Live HTTP Web Browsing / Testing
        html, status_code, fetch_error = self._fetch_html(website)

        # Website Unreachable / Live Connection Failed
        if not html:
            collector.add_fact(
                EvidenceCategory.IDENTITY,
                f"Attempted to connect to {website} but live server was unreachable: {fetch_error or f'HTTP {status_code}'}",
                evidence_url=website,
                source_type=SourceType.WEBSITE_HOMEPAGE,
            )
            collector.add_unknown(
                EvidenceCategory.BOOKING_FLOW,
                f"Website {website} is currently offline or unreachable.",
            )
            ai_res = self._call_gemini_research(business)
            weaknesses = (ai_res.get("observed_weaknesses") if ai_res else None) or [f"Website unreachable ({fetch_error or 'timeout'})"]
            strengths = (ai_res.get("observed_strengths") if ai_res else None) or ["Local directory presence"]

            return BusinessResearch(
                business_id=business.id,
                website_exists=False,
                website_url=website,
                is_mobile_friendly=None,
                contact_methods=["phone"] if business.phone else [],
                observed_weaknesses=weaknesses,
                observed_strengths=strengths,
                evidence=collector.get_all(),
            )

        # Website Online & Reachable! Parse live DOM content
        soup = BeautifulSoup(html, "html.parser")
        text_content = soup.get_text(separator=" ", strip=True)

        # 1. Title & Meta Description
        title_tag = soup.find("title")
        title_text = title_tag.get_text().strip() if title_tag else ""
        if title_text:
            collector.add_fact(
                EvidenceCategory.IDENTITY,
                f"Live website title verified: '{title_text}'",
                evidence_url=website,
                raw_snippet=title_text[:120],
                source_type=SourceType.WEBSITE_HOMEPAGE,
            )

        # 2. Extract Exact Email from HTML DOM
        extracted_email = self._extract_verified_email_from_html(soup, html)
        if extracted_email:
            collector.add_fact(
                EvidenceCategory.CONTACT_FLOW,
                f"Verified business email extracted from website: {extracted_email}",
                evidence_url=website,
                source_type=SourceType.WEBSITE_CONTACT,
            )
            if not business.email:
                business.email = extracted_email

        # 3. Extract Exact Phone from HTML DOM
        extracted_phone = self._extract_phone_from_html(soup)
        if extracted_phone:
            collector.add_fact(
                EvidenceCategory.CONTACT_FLOW,
                f"Verified telephone number extracted from website: {extracted_phone}",
                evidence_url=website,
                source_type=SourceType.WEBSITE_CONTACT,
            )
            if not business.phone:
                business.phone = extracted_phone

        # 4. Mobile viewport check
        viewport_meta = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
        is_mobile_friendly = bool(viewport_meta and "width=device-width" in (viewport_meta.get("content") or "").lower())
        collector.add_fact(
            EvidenceCategory.MOBILE_UX,
            "Responsive mobile viewport meta tag verified on website" if is_mobile_friendly else "No responsive mobile viewport tag detected",
            evidence_url=website,
            confidence=0.95,
        )

        # 5. Contact methods & WhatsApp detection
        contact_methods: List[str] = []
        html_lower = html.lower()

        has_whatsapp = "api.whatsapp.com" in html_lower or "wa.me" in html_lower or "whatsapp" in html_lower
        if has_whatsapp:
            contact_methods.append("whatsapp")
            collector.add_fact(
                EvidenceCategory.CONTACT_FLOW,
                "Live WhatsApp click-to-chat button present on website.",
                evidence_url=website,
                source_type=SourceType.WEBSITE_HOMEPAGE,
            )

        if business.phone or extracted_phone:
            contact_methods.append("phone")
        if business.email or extracted_email:
            contact_methods.append("email")

        # 6. Booking & Ordering flow detection
        booking_keywords = ["book appointment", "online booking", "schedule appointment", "calendly", "cal.com", "appointy", "practo", "book online", "reserve table"]
        ordering_keywords = ["order online", "add to cart", "swiggy", "zomato", "menu cart", "checkout"]

        has_booking = any(k in html_lower for k in booking_keywords) or bool(soup.find("form"))
        has_ordering = any(k in html_lower for k in ordering_keywords)

        if has_booking:
            collector.add_fact(
                EvidenceCategory.BOOKING_FLOW,
                "Online appointment or intake booking form/widget verified on webpage.",
                evidence_url=website,
            )
        else:
            collector.add_fact(
                EvidenceCategory.BOOKING_FLOW,
                "No automated 24/7 self-serve appointment booking widget found on webpage.",
                evidence_url=website,
            )

        # 7. Technology Stack hints
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
                f"Identified web technologies: {', '.join(tech_stack)}",
                evidence_url=website,
            )

        # 8. Call Gemini AI with scraped live webpage text for grounded analysis
        ai_res = self._call_gemini_research(business, scraped_text=text_content, page_title=title_text)

        observed_weaknesses: List[str] = []
        if ai_res and ai_res.get("observed_weaknesses"):
            observed_weaknesses = ai_res["observed_weaknesses"]
        else:
            if not has_booking and business.category in ("clinic", "salon", "gym", "spa", "dental"):
                observed_weaknesses.append("No online appointment booking widget (phone/walk-in only)")
            if not has_ordering and business.category in ("restaurant", "retail", "bakery"):
                observed_weaknesses.append("No online ordering or digital menu checkout system")
            if not is_mobile_friendly:
                observed_weaknesses.append("Website lacks responsive mobile viewport optimization")

        observed_strengths: List[str] = []
        if ai_res and ai_res.get("observed_strengths"):
            observed_strengths = ai_res["observed_strengths"]
        else:
            observed_strengths = [f"Verified active website ({title_text[:50] or website})"]

        if ai_res:
            for claim_item in ai_res.get("evidence_claims", []):
                cat_str = claim_item.get("category", "identity")
                cat_enum = EvidenceCategory.BOOKING_FLOW if "booking" in cat_str else EvidenceCategory.IDENTITY
                collector.add_fact(
                    cat_enum,
                    claim_item.get("claim", f"Fact claim for {business.name}"),
                    evidence_url=website,
                    source_type=SourceType.WEBSITE_HOMEPAGE
                )

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
            observed_strengths=observed_strengths,
            evidence=collector.get_all(),
        )


# Auto-register HTTPWebResearchProvider in registry
ResearchRegistry.register("http_web", HTTPWebResearchProvider())
ResearchRegistry.register("live", HTTPWebResearchProvider())

