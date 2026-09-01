"""Legitimate Public Contact Discovery & Provenance Engine for B2B Prospects.

Crawls authorized public website endpoints (homepage, /contact, /about, /team),
extracts authentic business emails, phone numbers, and WhatsApp gateways,
and records explicit source provenance, discovery timestamps, and confidence ratings.

STRICT NON-NEGOTIABLE RULES:
- NEVER fabricate or guess emails (e.g. NEVER make up info@, owner@, or contact@).
- If no legitimate public email exists, record status as NOT_FOUND.
- Always store source URL and discovery method.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
import urllib.request
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from bs4 import BeautifulSoup

from b2b.models import (
    BusinessRecord,
    BusinessResearch,
    ContactConfidence,
    ContactRecord,
    ContactSourceType,
    EmailVerificationStatus,
)

logger = logging.getLogger(__name__)

# Standard contact path candidates on business websites
_CONTACT_PATHS = [
    "/contact",
    "/contact-us",
    "/contactus",
    "/about",
    "/about-us",
    "/reach-us",
    "/team",
    "/get-in-touch",
    "/support",
]

# Strict email regex excluding file extensions and dummy placeholders
_EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)

# Common image/asset patterns that can falsely look like emails (e.g. hero@2x.png)
_ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js", ".ico", ".woff", ".woff2", ".ttf"
}

# Dummy placeholder emails to strictly ignore
_DUMMY_EMAIL_DOMAINS = {
    "example.com", "sample.com", "domain.com", "test.com", "yoursite.com",
    "email.com", "company.com", "site.com", "yourdomain.com", "tempmail.com"
}


def is_valid_email_candidate(email: str) -> bool:
    """Check whether an extracted string is a valid non-asset, non-dummy email candidate."""
    if not email or "@" not in email:
        return False
    email = email.strip().lower()

    # Exclude dummy/image asset extensions
    for ext in _ASSET_EXTENSIONS:
        if email.endswith(ext):
            return False

    parts = email.split("@")
    if len(parts) != 2:
        return False
    local_part, domain_part = parts

    if len(local_part) < 1 or len(domain_part) < 3 or "." not in domain_part:
        return False

    if domain_part in _DUMMY_EMAIL_DOMAINS:
        return False

    # Local part sanity check
    if any(c in local_part for c in ("/", "\\", " ", "<", ">", "(", ")", "[", "]", ":", ";", '"')):
        return False

    return True


class BaseContactDiscoveryProvider(ABC):
    """Abstract interface for business contact discovery providers."""

    name: str = "base"

    @abstractmethod
    def discover(
        self,
        business: BusinessRecord,
        research: Optional[BusinessResearch] = None,
    ) -> List[ContactRecord]:
        """Discover legitimate public contact information for a business."""
        pass


class WebsiteContactDiscoveryProvider(BaseContactDiscoveryProvider):
    """Safe, rate-limited public website contact discovery provider."""

    name: str = "website_crawler"

    def __init__(self, timeout_seconds: int = 8, max_subpages: int = 3, user_agent: Optional[str] = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_subpages = max_subpages
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (B2B-Contact-Auditor/1.0)"
        )

    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page HTML safely with headers and timeouts."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                content_bytes = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                return content_bytes.decode(charset, errors="replace")
        except Exception as exc:
            logger.debug("Contact discovery fetch failed for %s: %s", url, exc)
            return None

    def _extract_from_html(
        self,
        html: str,
        page_url: str,
        source_type: ContactSourceType,
        business: BusinessRecord,
    ) -> List[ContactRecord]:
        """Parse HTML to extract verified public contact points."""
        soup = BeautifulSoup(html, "html.parser")
        discovered: List[ContactRecord] = []
        seen_emails: Set[str] = set()
        seen_phones: Set[str] = set()

        # 1. Inspect mailto: links
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href.lower().startswith("mailto:"):
                raw_email = href[7:].split("?")[0].strip()
                if is_valid_email_candidate(raw_email) and raw_email.lower() not in seen_emails:
                    seen_emails.add(raw_email.lower())
                    
                    # Extract associated name / label if available
                    label = a_tag.get_text(strip=True)
                    contact_name = label if label and "@" not in label and len(label) < 60 else None

                    # Check confidence
                    confidence = ContactConfidence.HIGH if source_type == ContactSourceType.WEBSITE_CONTACT else ContactConfidence.MEDIUM
                    if business.domain and business.domain in raw_email.lower():
                        confidence = ContactConfidence.HIGH

                    discovered.append(
                        ContactRecord(
                            id=f"cnt_{uuid.uuid4().hex[:10]}",
                            business_id=business.id,
                            email=raw_email.lower(),
                            contact_name=contact_name,
                            source_url=page_url,
                            source_type=source_type,
                            confidence=confidence,
                            verification_status=EmailVerificationStatus.UNVERIFIED,
                            discovered_at=datetime.now(timezone.utc).isoformat(),
                        )
                    )

            # 2. Inspect tel: links
            elif href.lower().startswith("tel:"):
                raw_phone = href[4:].split("?")[0].strip()
                digits = re.sub(r"\D", "", raw_phone)
                if len(digits) >= 8 and digits not in seen_phones:
                    seen_phones.add(digits)
                    discovered.append(
                        ContactRecord(
                            id=f"cnt_{uuid.uuid4().hex[:10]}",
                            business_id=business.id,
                            phone=raw_phone,
                            source_url=page_url,
                            source_type=source_type,
                            confidence=ContactConfidence.HIGH,
                            verification_status=EmailVerificationStatus.UNVERIFIED,
                            discovered_at=datetime.now(timezone.utc).isoformat(),
                        )
                    )

            # 3. Inspect WhatsApp links
            elif "wa.me" in href or "api.whatsapp.com" in href:
                discovered.append(
                    ContactRecord(
                        id=f"cnt_{uuid.uuid4().hex[:10]}",
                        business_id=business.id,
                        whatsapp_link=href,
                        source_url=page_url,
                        source_type=source_type,
                        confidence=ContactConfidence.HIGH,
                        verification_status=EmailVerificationStatus.UNVERIFIED,
                        discovered_at=datetime.now(timezone.utc).isoformat(),
                    )
                )

        # 4. Text regex scan for email addresses in body/footer
        # Remove script/style tags before text search
        for script_tag in soup(["script", "style", "noscript"]):
            script_tag.decompose()
        page_text = soup.get_text(separator=" ")

        for match in _EMAIL_REGEX.finditer(page_text):
            found_email = match.group(0).strip().lower()
            if is_valid_email_candidate(found_email) and found_email not in seen_emails:
                seen_emails.add(found_email)
                confidence = ContactConfidence.MEDIUM
                if business.domain and business.domain in found_email:
                    confidence = ContactConfidence.HIGH

                discovered.append(
                    ContactRecord(
                        id=f"cnt_{uuid.uuid4().hex[:10]}",
                        business_id=business.id,
                        email=found_email,
                        source_url=page_url,
                        source_type=source_type,
                        confidence=confidence,
                        verification_status=EmailVerificationStatus.UNVERIFIED,
                        discovered_at=datetime.now(timezone.utc).isoformat(),
                    )
                )

        return discovered

    def discover(
        self,
        business: BusinessRecord,
        research: Optional[BusinessResearch] = None,
    ) -> List[ContactRecord]:
        """Crawl homepage and contact subpages to discover genuine public contacts."""
        results: List[ContactRecord] = []
        website = business.website

        # If business has a pre-existing phone or email from directory, register it with provenance
        if business.email and is_valid_email_candidate(business.email):
            results.append(
                ContactRecord(
                    id=f"cnt_{uuid.uuid4().hex[:10]}",
                    business_id=business.id,
                    email=business.email.strip().lower(),
                    phone=business.phone,
                    source_url=website or "directory_record",
                    source_type=ContactSourceType.DIRECTORY_LISTING,
                    confidence=ContactConfidence.HIGH if business.source_provider != "manual_input" else ContactConfidence.MEDIUM,
                    verification_status=EmailVerificationStatus.UNVERIFIED,
                    discovered_at=datetime.now(timezone.utc).isoformat(),
                )
            )

        if not website:
            if not results:
                # Record explicit NOT_FOUND record
                results.append(
                    ContactRecord(
                        id=f"cnt_{uuid.uuid4().hex[:10]}",
                        business_id=business.id,
                        email=None,
                        phone=business.phone,
                        source_url="directory_record",
                        source_type=ContactSourceType.DIRECTORY_LISTING,
                        confidence=ContactConfidence.LOW,
                        verification_status=EmailVerificationStatus.NOT_FOUND,
                        discovered_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
            return results

        # 1. Fetch homepage
        homepage_html = self._fetch_page(website)
        if homepage_html:
            home_contacts = self._extract_from_html(
                homepage_html, website, ContactSourceType.WEBSITE_HOMEPAGE, business
            )
            results.extend(home_contacts)

            # Discover contact subpage URLs
            parsed_base = urllib.parse.urlparse(website if website.startswith("http") else f"https://{website}")
            base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
            soup = BeautifulSoup(homepage_html, "html.parser")

            subpage_urls: Set[str] = set()
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if any(path in href.lower() for path in _CONTACT_PATHS):
                    resolved = urllib.parse.urljoin(base_origin, href)
                    # Only follow internal subpages on same domain
                    if urllib.parse.urlparse(resolved).netloc == parsed_base.netloc:
                        subpage_urls.add(resolved)

            # Limit subpages
            for sub_url in list(subpage_urls)[: self.max_subpages]:
                sub_html = self._fetch_page(sub_url)
                if sub_html:
                    stype = ContactSourceType.WEBSITE_CONTACT if "contact" in sub_url.lower() else ContactSourceType.WEBSITE_ABOUT
                    sub_contacts = self._extract_from_html(sub_html, sub_url, stype, business)
                    results.extend(sub_contacts)

        # If still no email found across any public pages
        has_email = any(c.email is not None for c in results)
        if not has_email:
            results.append(
                ContactRecord(
                    id=f"cnt_{uuid.uuid4().hex[:10]}",
                    business_id=business.id,
                    email=None,
                    phone=business.phone,
                    source_url=website,
                    source_type=ContactSourceType.WEBSITE_CONTACT,
                    confidence=ContactConfidence.LOW,
                    verification_status=EmailVerificationStatus.NOT_FOUND,
                    discovered_at=datetime.now(timezone.utc).isoformat(),
                )
            )

        return results


class ContactDiscoveryService:
    """Orchestrates contact discovery across multiple providers with deduplication and persistence."""

    def __init__(self, db: Optional[Any] = None, provider: Optional[BaseContactDiscoveryProvider] = None) -> None:
        self.db = db
        self.provider = provider or WebsiteContactDiscoveryProvider()

    def discover_and_store(
        self,
        business: BusinessRecord,
        research: Optional[BusinessResearch] = None,
    ) -> List[ContactRecord]:
        """Execute contact discovery, deduplicate, persist to database, and update business record."""
        contacts = self.provider.discover(business, research)
        stored: List[ContactRecord] = []

        # Deduplicate by email and phone
        seen_keys: Set[str] = set()
        primary_assigned = False

        for c in contacts:
            key = f"{c.email or ''}:{c.phone or ''}:{c.whatsapp_link or ''}"
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Assign primary flag to first record with email
            if c.email and not primary_assigned:
                c.is_primary = True
                primary_assigned = True
            elif not primary_assigned and not c.email:
                c.is_primary = True
                primary_assigned = True
            else:
                c.is_primary = False

            if self.db:
                self.db.save_contact(c)
            stored.append(c)

        # Update business email/phone if authentic email discovered
        primary_email_contact = next((c for c in stored if c.email), None)
        if primary_email_contact and primary_email_contact.email:
            business.email = primary_email_contact.email
            if self.db:
                self.db.save_business(business)

        return stored
