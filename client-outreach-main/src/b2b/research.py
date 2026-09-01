"""Research Interfaces and Evidence Collection Contracts for B2B Business Intelligence."""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from b2b.models import (
    BusinessRecord,
    BusinessResearch,
    ClaimType,
    EvidenceCategory,
    ResearchEvidence,
    SourceType,
)

logger = logging.getLogger(__name__)


class EvidenceCollector:
    """Helper to assemble verified research claims with strict provenance."""

    def __init__(self, business_id: str) -> None:
        self.business_id = business_id
        self._evidence: List[ResearchEvidence] = []

    def add_fact(
        self,
        category: EvidenceCategory,
        claim: str,
        *,
        evidence_url: Optional[str] = None,
        raw_snippet: Optional[str] = None,
        source_type: SourceType = SourceType.WEBSITE_HOMEPAGE,
        confidence: float = 1.0,
    ) -> ResearchEvidence:
        """Record a verified factual observation backed by a source URL or snippet."""
        ev = ResearchEvidence(
            id=f"ev_{uuid.uuid4().hex[:12]}",
            business_id=self.business_id,
            category=category,
            claim=claim.strip(),
            claim_type=ClaimType.VERIFIED_FACT,
            evidence_url=evidence_url,
            raw_snippet=raw_snippet.strip() if raw_snippet else None,
            source_type=source_type,
            confidence=max(0.0, min(1.0, confidence)),
            collected_at=datetime.now(timezone.utc).isoformat(),
        )
        self._evidence.append(ev)
        return ev

    def add_inference(
        self,
        category: EvidenceCategory,
        claim: str,
        *,
        evidence_url: Optional[str] = None,
        raw_snippet: Optional[str] = None,
        source_type: SourceType = SourceType.WEBSITE_HOMEPAGE,
        confidence: float = 0.7,
    ) -> ResearchEvidence:
        """Record an analytical inference derived from observed facts."""
        ev = ResearchEvidence(
            id=f"ev_{uuid.uuid4().hex[:12]}",
            business_id=self.business_id,
            category=category,
            claim=claim.strip(),
            claim_type=ClaimType.AI_INFERENCE,
            evidence_url=evidence_url,
            raw_snippet=raw_snippet.strip() if raw_snippet else None,
            source_type=source_type,
            confidence=max(0.0, min(1.0, confidence)),
            collected_at=datetime.now(timezone.utc).isoformat(),
        )
        self._evidence.append(ev)
        return ev

    def add_unknown(
        self,
        category: EvidenceCategory,
        claim: str,
        *,
        source_type: SourceType = SourceType.WEBSITE_HOMEPAGE,
    ) -> ResearchEvidence:
        """Explicitly record unverified or missing information to avoid hallucination."""
        ev = ResearchEvidence(
            id=f"ev_{uuid.uuid4().hex[:12]}",
            business_id=self.business_id,
            category=category,
            claim=claim.strip(),
            claim_type=ClaimType.UNKNOWN,
            evidence_url=None,
            raw_snippet=None,
            source_type=source_type,
            confidence=0.0,
            collected_at=datetime.now(timezone.utc).isoformat(),
        )
        self._evidence.append(ev)
        return ev

    def get_all(self) -> List[ResearchEvidence]:
        return list(self._evidence)

    def get_facts(self) -> List[ResearchEvidence]:
        return [e for e in self._evidence if e.claim_type == ClaimType.VERIFIED_FACT]

    def get_inferences(self) -> List[ResearchEvidence]:
        return [e for e in self._evidence if e.claim_type == ClaimType.AI_INFERENCE]

    def get_unknowns(self) -> List[ResearchEvidence]:
        return [e for e in self._evidence if e.claim_type == ClaimType.UNKNOWN]


class BaseResearchProvider(ABC):
    """Abstract interface for business research providers."""

    name: str = "base_research"

    @abstractmethod
    def research(self, business: BusinessRecord, **kwargs: Any) -> BusinessResearch:
        """Perform comprehensive public digital presence research on a business."""
        pass


class ResearchRegistry:
    """Registry managing available research providers."""

    _providers: Dict[str, BaseResearchProvider] = {}

    @classmethod
    def register(cls, name: str, provider: BaseResearchProvider) -> None:
        cls._providers[name] = provider

    @classmethod
    def get(cls, name: str) -> Optional[BaseResearchProvider]:
        return cls._providers.get(name)

    @classmethod
    def list_providers(cls) -> List[str]:
        return list(cls._providers.keys())