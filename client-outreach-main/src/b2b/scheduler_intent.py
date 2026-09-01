"""Scheduler Intent Layer for Automated B2B Acquisition Cycles."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence

from b2b.models import (
    BusinessRecord,
    BusinessResearch,
    DemoRecord,
    OpportunityRecord,
    OutreachRecord,
    OutreachResponse,
)

logger = logging.getLogger(__name__)


class BusinessCycleContext:
    """Carries context across a single scheduled automation cycle."""

    def __init__(self, cycle_id: str) -> None:
        self.cycle_id = cycle_id
        self.discovered: List[BusinessRecord] = []
        self.researched: List[BusinessResearch] = []
        self.opportunities: List[OpportunityRecord] = []
        self.demos: List[DemoRecord] = []
        self.outreach_drafts: List[OutreachRecord] = []
        self.responses_processed: List[OutreachResponse] = []
        self.errors: List[str] = []
        self.stats: Dict[str, Any] = {}


class BusinessPipelineIntent(ABC):
    """Protocol defining the stages of an autonomous B2B acquisition cycle."""

    @abstractmethod
    def run_discovery_step(self, ctx: BusinessCycleContext, *, limit: int = 10, **kwargs: Any) -> List[BusinessRecord]:
        """Discover new qualified candidate businesses."""
        pass

    @abstractmethod
    def run_research_step(self, ctx: BusinessCycleContext, businesses: Sequence[BusinessRecord]) -> List[BusinessResearch]:
        """Perform verified digital presence research on discovered businesses."""
        pass

    @abstractmethod
    def run_analysis_step(self, ctx: BusinessCycleContext, research_list: Sequence[BusinessResearch]) -> List[OpportunityRecord]:
        """Identify concrete operational gaps and calculate opportunity scores."""
        pass

    @abstractmethod
    def run_demo_step(self, ctx: BusinessCycleContext, opportunities: Sequence[OpportunityRecord]) -> List[DemoRecord]:
        """Generate interactive tailored web/app prototypes for qualified opportunities."""
        pass

    @abstractmethod
    def run_outreach_step(self, ctx: BusinessCycleContext, demos: Sequence[DemoRecord]) -> List[OutreachRecord]:
        """Generate personalized email outreach drafts and place into approval queue."""
        pass

    @abstractmethod
    def run_response_tracking_step(self, ctx: BusinessCycleContext) -> List[OutreachResponse]:
        """Sync and classify inbound responses."""
        pass