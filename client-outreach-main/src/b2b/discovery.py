"""Discovery Interfaces, Providers, Deduplication, and Service Engine for B2B Business Acquisition."""

from __future__ import annotations

import csv
import io
import logging
import re
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING
from urllib.parse import urlparse
from pydantic import BaseModel, Field

from b2b.models import BusinessRecord, BusinessStatus

if TYPE_CHECKING:
    from db.database import Database

logger = logging.getLogger(__name__)


def clean_domain(url: Optional[str]) -> Optional[str]:
    """Extract canonical lowercased domain without www., port, or paths."""
    if not url:
        return None
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower().split(":")[0]
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc if netloc else None
    except Exception:
        return None


def clean_phone(phone: Optional[str]) -> Optional[str]:
    """Normalize phone numbers by stripping country codes (+91), dashes, spaces, and leading zeros."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits if len(digits) >= 8 else None


def _slugify(text: str) -> str:
    """Generate a clean URL/ID slug from text."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text.strip("_")


class BusinessDeduplicator:
    """Detects exact and fuzzy duplicate businesses across names, domains, and cities."""

    def __init__(self, existing_businesses: Optional[Sequence[BusinessRecord]] = None) -> None:
        self._existing: List[BusinessRecord] = list(existing_businesses or [])
        self._domains: set[str] = {
            b.domain for b in self._existing if b.domain
        }
        self._name_city_pairs: set[Tuple[str, str]] = {
            (self._normalize_name(b.name), b.city.strip().lower())
            for b in self._existing
            if b.name and b.city
        }

    @staticmethod
    def _normalize_name(name: str) -> str:
        name = name.lower()
        name = re.sub(r"[^\w\s]", "", name)
        # remove common corporate/business suffixes
        suffixes = {"pvt", "ltd", "llp", "inc", "co", "clinic", "center", "centre", "academy", "classes"}
        tokens = [t for t in name.split() if t not in suffixes]
        return " ".join(tokens)

    def is_duplicate(self, candidate: BusinessRecord) -> Tuple[bool, Optional[str]]:
        """Check whether a candidate business already exists."""
        # 1. Exact domain check
        if candidate.domain and candidate.domain in self._domains:
            return True, f"Domain duplicate: {candidate.domain}"

        # 2. Exact (normalized name, city) check
        cand_norm = self._normalize_name(candidate.name)
        cand_city = candidate.city.strip().lower()
        if (cand_norm, cand_city) in self._name_city_pairs:
            return True, f"Name & City duplicate: {candidate.name} in {candidate.city}"

        # 3. Token-similarity fuzzy check in same city
        cand_tokens = set(cand_norm.split())
        if cand_tokens:
            for b in self._existing:
                if b.city.strip().lower() == cand_city:
                    exist_norm = self._normalize_name(b.name)
                    exist_tokens = set(exist_norm.split())
                    if exist_tokens:
                        intersection = cand_tokens.intersection(exist_tokens)
                        union = cand_tokens.union(exist_tokens)
                        jaccard = len(intersection) / len(union) if union else 0.0
                        if jaccard >= 0.75:
                            return True, f"Fuzzy name duplicate ({jaccard:.2f}) with '{b.name}' in {b.city}"

        return False, None

    def register(self, business: BusinessRecord) -> None:
        """Register a new business into the in-memory deduplication index."""
        self._existing.append(business)
        if business.domain:
            self._domains.add(business.domain)
        if business.name and business.city:
            self._name_city_pairs.add((self._normalize_name(business.name), business.city.strip().lower()))


class BaseDiscoveryProvider(ABC):
    """Abstract interface for business discovery providers."""

    name: str = "base_discovery"

    @abstractmethod
    def discover(
        self,
        *,
        category: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> List[BusinessRecord]:
        """Discover candidate businesses matching criteria."""
        pass


class CSVLeadDiscoveryProvider(BaseDiscoveryProvider):
    """Parses and ingests Indian business records from CSV files."""

    name: str = "csv_import"

    # Header aliases mapping to canonical fields
    FIELD_ALIASES: Dict[str, Tuple[str, ...]] = {
        "name": ("name", "business_name", "company", "company_name", "title", "store_name", "clinic_name"),
        "city": ("city", "location", "city_name", "town", "district"),
        "state": ("state", "province", "region"),
        "country": ("country", "nation"),
        "category": ("category", "vertical", "industry", "type", "business_type", "niche"),
        "website": ("website", "site", "url", "web", "web_address", "homepage"),
        "phone": ("phone", "mobile", "telephone", "contact", "contact_number", "phone_number", "tel"),
        "email": ("email", "email_id", "contact_email", "mail"),
        "address": ("address", "street", "full_address", "location_address"),
    }

    def _normalize_header(self, header: str) -> str:
        h = header.strip().lower().replace(" ", "_").replace("-", "_")
        for canon, aliases in self.FIELD_ALIASES.items():
            if h in aliases:
                return canon
        return h

    def discover(
        self,
        *,
        file_path: Optional[str | Path] = None,
        csv_content: Optional[str] = None,
        category: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 100,
        **kwargs: Any,
    ) -> List[BusinessRecord]:
        """Parse businesses from a CSV file path or raw CSV string."""
        if not file_path and not csv_content:
            raise ValueError("CSVLeadDiscoveryProvider requires either 'file_path' or 'csv_content'.")

        if file_path:
            p = Path(file_path)
            if not p.exists():
                raise FileNotFoundError(f"CSV file not found: {p}")
            text = p.read_text(encoding="utf-8", errors="replace")
        else:
            text = csv_content or ""

        # Detect delimiter (comma, semicolon, tab)
        sample = text[:2048]
        delimiter = ","
        if sample:
            try:
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample, delimiters=",\t;|")
                delimiter = dialect.delimiter
            except Exception:
                delimiter = ","

        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        raw_headers = next(reader, None)
        if not raw_headers:
            return []

        header_map = [self._normalize_header(h) for h in raw_headers]
        results: List[BusinessRecord] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for row_idx, row in enumerate(reader, start=2):
            if not row or not any(row):
                continue
            row_dict: Dict[str, str] = {}
            for col_idx, val in enumerate(row):
                if col_idx < len(header_map):
                    key = header_map[col_idx]
                    row_dict[key] = val.strip()

            name = row_dict.get("name")
            if not name:
                continue

            row_city = row_dict.get("city") or city or "Unknown"
            row_category = row_dict.get("category") or category or "general_smb"

            # Optional filter matching
            if city and city.lower() != "all" and row_city.strip().lower() != city.strip().lower():
                continue
            if category and category.lower() != "all" and row_category.strip().lower() != category.strip().lower():
                continue

            website = row_dict.get("website") or None
            domain = clean_domain(website) if website else None
            phone = clean_phone(row_dict.get("phone")) if row_dict.get("phone") else None
            email = row_dict.get("email") or None
            address = row_dict.get("address") or None
            state = row_dict.get("state") or None
            country = row_dict.get("country") or "India"

            # Generate deterministic ID
            slug_name = _slugify(name)[:30]
            slug_city = _slugify(row_city)[:20]
            biz_id = f"biz_{slug_name}_{slug_city}" if slug_name and slug_city else f"biz_{uuid.uuid4().hex[:12]}"

            rec = BusinessRecord(
                id=biz_id,
                name=name,
                category=row_category,
                city=row_city,
                state=state,
                country=country,
                address=address,
                website=website,
                domain=domain,
                phone=phone,
                email=email,
                source_provider="csv_import",
                source_id=f"{Path(file_path).name if file_path else 'csv'}:row_{row_idx}",
                status=BusinessStatus.DISCOVERED,
                created_at=now_iso,
                updated_at=now_iso,
            )
            results.append(rec)
            if len(results) >= limit:
                break

        return results


class ManualLeadDiscoveryProvider(BaseDiscoveryProvider):
    """Adds single target businesses directly via explicit parameters."""

    name: str = "manual_input"

    def discover(
        self,
        *,
        name: Optional[str] = None,
        city: Optional[str] = None,
        category: Optional[str] = None,
        website: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        state: Optional[str] = None,
        country: str = "India",
        limit: int = 1,
        **kwargs: Any,
    ) -> List[BusinessRecord]:
        if not name or not city:
            raise ValueError("ManualLeadDiscoveryProvider requires 'name' and 'city'.")

        now_iso = datetime.now(timezone.utc).isoformat()
        slug_name = _slugify(name)[:30]
        slug_city = _slugify(city)[:20]
        biz_id = f"biz_{slug_name}_{slug_city}"

        rec = BusinessRecord(
            id=biz_id,
            name=name.strip(),
            category=category.strip() if category else "general_smb",
            city=city.strip(),
            state=state.strip() if state else None,
            country=country.strip() if country else "India",
            address=address.strip() if address else None,
            website=website.strip() if website else None,
            domain=clean_domain(website),
            phone=clean_phone(phone),
            email=email.strip() if email else None,
            source_provider="manual_input",
            source_id="cli_manual",
            status=BusinessStatus.DISCOVERED,
            created_at=now_iso,
            updated_at=now_iso,
        )
        return [rec]


class LiveWebDiscoveryProvider(BaseDiscoveryProvider):
    """Fetches real local business leads live from OpenStreetMap and live web search registries."""

    name: str = "live_web"

    # Search keywords per category
    CATEGORY_KEYWORDS: Dict[str, List[str]] = {
        "clinic": ["clinic", "hospital", "dental clinic", "eye care clinic"],
        "healthcare": ["clinic", "hospital", "diagnostic center"],
        "restaurant": ["restaurant", "cafe", "fine dining", "bakery"],
        "salon": ["salon", "spa", "hair salon", "beauty parlour"],
        "coaching": ["coaching institute", "academy", "classes", "learning center"],
        "gym": ["gym", "fitness center", "crossfit"],
        "retail": ["store", "supermarket", "grocery", "boutique"],
        "real_estate": ["real estate agency", "property consultant", "builders"],
        "general_smb": ["services", "consultant", "agency"],
    }

    def discover(
        self,
        *,
        category: Optional[str] = None,
        city: Optional[str] = None,
        location: Optional[str] = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> List[BusinessRecord]:
        import json
        import re
        import urllib.request
        from urllib.parse import quote_plus, unquote

        target_location = (location or city or "Ahmedabad").strip()
        target_city = city.strip() if city else target_location.split(",")[-1].strip()
        target_cat = (category or "clinic").strip().lower()
        keywords = self.CATEGORY_KEYWORDS.get(target_cat, [target_cat])

        results: List[BusinessRecord] = []
        seen_names: set[str] = set()
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Query OpenStreetMap Nominatim per keyword
        for kw in keywords:
            if len(results) >= limit:
                break
            full_query = f"{kw} in {target_location}, India"
            url = f"https://nominatim.openstreetmap.org/search?q={quote_plus(full_query)}&format=json&extratags=1&addressdetails=1&limit=25"

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) B2BOutreachBot/1.0",
                    "Accept": "application/json",
                },
            )

            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    raw_data = response.read().decode("utf-8")
                    parsed_json = json.loads(raw_data)
                    data = parsed_json if isinstance(parsed_json, list) else []
            except Exception as exc:
                logger.warning(f"OSM query failed for '{full_query}': {exc}")
                data = []

            for idx, item in enumerate(data):
                if len(results) >= limit:
                    break
                namedetails = item.get("namedetails") or {}
                display_name = item.get("display_name", "")
                raw_name = namedetails.get("name") or item.get("name")
                if not raw_name and display_name:
                    raw_name = display_name.split(",")[0].strip()
                if not raw_name or len(raw_name) < 3 or raw_name.lower() in seen_names:
                    continue

                seen_names.add(raw_name.lower())
                extratags = item.get("extratags") or {}
                address_info = item.get("address") or {}

                website = (
                    extratags.get("website")
                    or extratags.get("contact:website")
                    or extratags.get("url")
                )
                phone = (
                    extratags.get("phone")
                    or extratags.get("contact:phone")
                    or extratags.get("mobile")
                )
                email = extratags.get("email") or extratags.get("contact:email")

                # Live enrichment if website/phone/email missing from OSM
                if not website or not phone or not email:
                    try:
                        enriched_web, enriched_phone, enriched_email = self._enrich_lead_contact(raw_name, target_city)
                        website = website or enriched_web
                        phone = phone or enriched_phone
                        email = email or enriched_email
                    except Exception:
                        pass

                road = address_info.get("road") or address_info.get("suburb") or ""
                city_name = address_info.get("city") or address_info.get("town") or address_info.get("state_district") or target_city
                state_name = address_info.get("state") or "Gujarat"
                full_addr = f"{road}, {city_name}".strip(", ") if road else f"{city_name}, {state_name}"

                slug_name = _slugify(raw_name)[:30]
                slug_city = _slugify(city_name)[:20]
                biz_id = f"biz_live_{slug_name}_{slug_city}" if slug_name else f"biz_live_{uuid.uuid4().hex[:10]}"

                rec = BusinessRecord(
                    id=biz_id,
                    name=raw_name.strip(),
                    category=target_cat,
                    city=city_name,
                    state=state_name,
                    country="India",
                    address=full_addr,
                    website=website,
                    domain=clean_domain(website),
                    phone=clean_phone(phone),
                    email=email,
                    source_provider="osm_live",
                    source_id=f"osm:{item.get('osm_id', idx)}",
                    status=BusinessStatus.DISCOVERED,
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                results.append(rec)

    @staticmethod
    def _enrich_lead_contact(name: str, city: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Query public search index to extract real website URL, phone number, and contact email."""
        import json
        import urllib.request
        from urllib.parse import quote_plus

        q = f"{name} {city} contact phone website email"
        url = f"https://nominatim.openstreetmap.org/search?q={quote_plus(q)}&format=json&extratags=1&limit=3"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) B2BOutreachBot/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for item in data:
                ext = item.get("extratags") or {}
                w = ext.get("website") or ext.get("contact:website") or ext.get("url")
                p = ext.get("phone") or ext.get("contact:phone") or ext.get("mobile")
                e = ext.get("email") or ext.get("contact:email")
                if w or p or e:
                    return w, p, e
        except Exception:
            pass
        return None, None, None


class GooglePlacesDiscoveryProvider(BaseDiscoveryProvider):
    """Google Places API discovery provider for verified local business directories."""

    name: str = "google_places"

    def __init__(self, api_key: Optional[str] = None) -> None:
        import os
        self.api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY", "")

    def discover(
        self,
        *,
        category: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> List[BusinessRecord]:
        if not self.api_key:
            logger.info("GOOGLE_PLACES_API_KEY not configured; falling back to OpenStreetMap / Live discovery.")
            return LiveWebDiscoveryProvider().discover(category=category, city=city, limit=limit, **kwargs)

        import json
        import urllib.parse
        import urllib.request

        target_city = city or "Ahmedabad"
        target_cat = category or "clinic"
        query = f"{target_cat} in {target_city}, India"
        url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={urllib.parse.quote_plus(query)}&key={self.api_key}"

        results: List[BusinessRecord] = []
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for item in data.get("results", [])[:limit]:
                    name = item.get("name", "")
                    addr = item.get("formatted_address", f"{target_city}, India")
                    slug_name = _slugify(name)[:30]
                    biz_id = f"biz_gp_{slug_name}_{_slugify(target_city)[:15]}"
                    now_iso = datetime.now(timezone.utc).isoformat()
                    results.append(
                        BusinessRecord(
                            id=biz_id,
                            name=name,
                            category=target_cat,
                            city=target_city,
                            country="India",
                            address=addr,
                            source_provider="google_places",
                            source_id=item.get("place_id"),
                            status=BusinessStatus.DISCOVERED,
                            created_at=now_iso,
                            updated_at=now_iso,
                        )
                    )
        except Exception as exc:
            logger.warning(f"Google Places API query failed: {exc}")

        return results


class NominatimDiscoveryProvider(LiveWebDiscoveryProvider):
    """Direct alias for OpenStreetMap Nominatim discovery engine."""
    name: str = "nominatim"


class DiscoveryRegistry:
    """Registry managing available discovery providers."""

    _providers: Dict[str, BaseDiscoveryProvider] = {}

    @classmethod
    def register(cls, name: str, provider: BaseDiscoveryProvider) -> None:
        cls._providers[name.lower()] = provider

    @classmethod
    def get(cls, name: str) -> Optional[BaseDiscoveryProvider]:
        return cls._providers.get(name.lower())

    @classmethod
    def list_providers(cls) -> List[str]:
        return list(cls._providers.keys())


# Auto-register default providers
_live_provider = LiveWebDiscoveryProvider()
_google_places = GooglePlacesDiscoveryProvider()
_nominatim = NominatimDiscoveryProvider()

DiscoveryRegistry.register("csv", CSVLeadDiscoveryProvider())
DiscoveryRegistry.register("csv_import", CSVLeadDiscoveryProvider())
DiscoveryRegistry.register("manual", ManualLeadDiscoveryProvider())
DiscoveryRegistry.register("manual_input", ManualLeadDiscoveryProvider())
DiscoveryRegistry.register("live", _live_provider)
DiscoveryRegistry.register("live_web", _live_provider)
DiscoveryRegistry.register("web", _live_provider)
DiscoveryRegistry.register("osm", _live_provider)
DiscoveryRegistry.register("osm_live", _live_provider)
DiscoveryRegistry.register("nominatim", _nominatim)
DiscoveryRegistry.register("google_places", _google_places)
DiscoveryRegistry.register("google", _google_places)



class DiscoveryResult(BaseModel):
    """Summary of a discovery and ingestion operation."""
    provider: str
    total_discovered: int
    total_saved: int
    total_duplicates: int
    businesses: List[BusinessRecord] = Field(default_factory=list)
    duplicates: List[Dict[str, str]] = Field(default_factory=list)


class DiscoveryService:
    """Coordinates business discovery, deduplication, and SQLite persistence."""

    def __init__(self, db: Database, deduplicator: Optional[BusinessDeduplicator] = None) -> None:
        self.db = db
        self.deduplicator = deduplicator

    def ingest_leads(
        self,
        provider_name: str = "csv",
        *,
        category: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 100,
        **provider_kwargs: Any,
    ) -> DiscoveryResult:
        """Discover leads using specified provider, deduplicate against DB, and save."""
        provider = DiscoveryRegistry.get(provider_name)
        if not provider:
            raise ValueError(f"Unknown discovery provider: '{provider_name}'. Available: {DiscoveryRegistry.list_providers()}")

        # Discover candidate records
        discovered_leads = provider.discover(
            category=category,
            city=city,
            limit=limit,
            **provider_kwargs,
        )

        # Initialize deduplicator with existing DB records if not provided
        if self.deduplicator is None:
            existing = self.db.list_businesses(limit=10000)
            self.deduplicator = BusinessDeduplicator(existing)

        saved_leads: List[BusinessRecord] = []
        duplicate_entries: List[Dict[str, str]] = []

        for lead in discovered_leads:
            is_dup, reason = self.deduplicator.is_duplicate(lead)
            if is_dup:
                duplicate_entries.append({
                    "id": lead.id,
                    "name": lead.name,
                    "city": lead.city,
                    "reason": reason or "Duplicate lead",
                })
                logger.info(f"Skipping duplicate lead: {lead.name} ({lead.city}) - {reason}")
            else:
                self.deduplicator.register(lead)
                saved = self.db.save_business(lead)
                saved_leads.append(saved)

        return DiscoveryResult(
            provider=provider_name,
            total_discovered=len(discovered_leads),
            total_saved=len(saved_leads),
            total_duplicates=len(duplicate_entries),
            businesses=saved_leads,
            duplicates=duplicate_entries,
        )