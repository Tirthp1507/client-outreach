"""Coherent Business Intelligence pipeline implementing BusinessPipelineIntent.

This is the Ryan-side bundle Jim wires into his scheduler cycle: one class that
turns researched businesses into scored opportunities, generated demos,
personalized outreach drafts (approval queue), classified responses, staged
follow-ups, and feedback reports - all via the shared b2b models and db CRUD.

Nothing is sent anywhere here. Every outbound artifact lands in the human
approval queue (PENDING_REVIEW) and must pass the OutreachGatekeeper before any
provider can dispatch it (Jim's infra).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from b2b.analyst import BusinessAnalyst, AnalysisResult
from b2b.demo_generator import DemoGenerator, DemoStrategy
from b2b.feedback import FeedbackReport, OutreachFeedbackEngine
from b2b.followup import FollowUpIntelligence, FollowUpPlan, FollowUpPolicy
from b2b.models import (
    BusinessRecord,
    BusinessResearch,
    BusinessStatus,
    DemoRecord,
    FollowUpRecord,
    FollowUpStatus,
    OpportunityRecord,
    OpportunityType,
    OutreachRecord,
    OutreachResponse,
    QualificationStatus,
    ReplyStatus,
    ResponseClassification,
)
from b2b.outreach import OutreachGenerator
from b2b.quality import DemoQualityChecker, OutreachQualityChecker
from b2b.response_classifier import ClassifiedResponse, ResponseClassifier
from b2b.scoring import OpportunityScorer, ScoredOpportunity
from b2b.scheduler_intent import BusinessCycleContext, BusinessPipelineIntent
from config import PROJECT_ROOT, get_config

# NOTE: `db.database.Database` is imported lazily inside methods to avoid the
# db.database <-> b2b.models <-> b2b package init import cycle (its `db` type
# hint is only a string annotation under `from __future__ import annotations`).

logger = logging.getLogger(__name__)


class BusinessIntelligenceService(BusinessPipelineIntent):
    """End-to-end intelligence implementation for the acquisition cycle."""

    def __init__(
        self,
        db: Database,
        *,
        analyst: Optional[BusinessAnalyst] = None,
        scorer: Optional[OpportunityScorer] = None,
        demo_generator: Optional[DemoGenerator] = None,
        outreach_generator: Optional[OutreachGenerator] = None,
        classifier: Optional[ResponseClassifier] = None,
        followup: Optional[FollowUpIntelligence] = None,
        feedback: Optional[OutreachFeedbackEngine] = None,
        config: Optional[dict] = None,
    ) -> None:
        self.db = db
        self.analyst = analyst or BusinessAnalyst()
        self.scorer = scorer or OpportunityScorer()
        self.demo_generator = demo_generator or DemoGenerator()
        self.outreach_generator = outreach_generator or OutreachGenerator()
        self.classifier = classifier or ResponseClassifier()
        self.followup = followup or FollowUpIntelligence()
        self.feedback = feedback or OutreachFeedbackEngine()
        self.quality_outreach = OutreachQualityChecker()
        self.quality_demo = DemoQualityChecker()

        cfg = config or dict(get_config().get("b2b") or {})
        self.min_demo_score = float(cfg.get("min_demo_score", 60.0))
        self.variants = int(cfg.get("outreach_variants", 2))
        self.followup_policy = FollowUpPolicy(
            cadence_days=list(cfg.get("followup_cadence_days", [3, 7])),
            max_followups=int(cfg.get("followup_max", 2)),
            enabled=bool(cfg.get("followup_enabled", True)),
        )

    # -- scheduler intent steps ------------------------------------------
    def run_analysis_step(
        self,
        ctx: BusinessCycleContext,
        research_list: Sequence[BusinessResearch],
        **kwargs: Any,
    ) -> List[OpportunityRecord]:
        """Analyze + score researched businesses into persisted opportunities."""
        print(f"\n🤖 [PHASE 3: AI OPPORTUNITY SCORING] Scoring {len(research_list)} business dossiers...")
        records: List[OpportunityRecord] = []
        for idx, research in enumerate(research_list, 1):
            business = self.db.get_business(research.business_id)
            if business is None:
                ctx.errors.append(f"run_analysis_step: no business {research.business_id}")
                continue
            result = self.analyst.analyze(business, research)
            if not result.sufficient_evidence:
                ctx.stats.setdefault("insufficient_evidence", []).append(
                    {"business_id": business.id, "reason": result.insufficient_reason})
                self.db.update_business_status(business.id, BusinessStatus.ANALYZED)
                print(f"  [{idx}/{len(research_list)}] {business.name}: Insufficient evidence ({result.insufficient_reason})")
                continue
            scored = self.scorer.score(result, business, research)
            if scored is None:
                continue
            opp = self._persist_opportunity(scored)
            records.append(opp)
            self.db.update_business_status(business.id, BusinessStatus.SCORED)
            print(f"  [{idx}/{len(research_list)}] {business.name} -> Score: {scored.score:.1f}/100 | Qualification: {opp.qualification_status.value} | Type: {opp.opportunity_type.value}")
            print(f"     ├─ Gap Identified: {opp.problem_summary[:80]}...")
            print(f"     └─ Proposed Solution: {opp.proposed_solution[:80]}...")
        ctx.opportunities.extend(records)
        ctx.stats["opportunities"] = len(records)
        print(f"  ▶ Phase 3 Complete: {len(records)} opportunities analyzed & scored.")
        return records

    def run_demo_step(
        self,
        ctx: BusinessCycleContext,
        opportunities: Sequence[OpportunityRecord],
        **kwargs: Any,
    ) -> List[DemoRecord]:
        """Generate real prototypes for QUALIFIED opportunities on/above the score floor."""
        print(f"\n🎨 [PHASE 4: 3-PAGE COMMERCIAL PROTOTYPE GENERATION] Generating prototypes for {len(opportunities)} qualified leads...")
        demos: List[DemoRecord] = []
        for idx, opp in enumerate(opportunities, 1):
            if opp.qualification_status != QualificationStatus.QUALIFIED:
                ctx.stats.setdefault("demos_skipped_not_qualified", []).append(opp.id)
                continue
            if opp.score < self.min_demo_score:
                ctx.stats.setdefault("demos_skipped_below_floor", []).append(opp.id)
                continue
            business = self.db.get_business(opp.business_id)
            if business is None:
                continue
            blueprint = DemoStrategy().blueprint(business, opp)
            demo = self.demo_generator.generate(business, opp, blueprint)
            qa = self.quality_demo.check(demo, artifact_root=PROJECT_ROOT)
            if not qa.passed:
                ctx.errors.append(f"demo quality gate failed for {demo.id}: {qa.issues}")
                print(f"  [{idx}/{len(opportunities)}] {business.name}: Demo QA failed ({qa.issues})")
                continue
            self.db.save_demo(demo)
            demos.append(demo)
            self.db.update_business_status(business.id, BusinessStatus.DEMO_READY)
            ctx.stats.setdefault("demo_stats", {})
            print(f"  [{idx}/{len(opportunities)}] {business.name} -> 3-Page Website Prototype Generated!")
            print(f"     ├─ Page 1: index.html (Home Showcase & Booker)")
            print(f"     ├─ Page 2: services.html (Interactive Rate Card)")
            print(f"     ├─ Page 3: about.html (Brand Story & Specialist Team)")
            print(f"     └─ Saved to: output/demos/{demo.id}/")
        ctx.demos.extend(demos)
        ctx.stats["demos"] = len(demos)
        print(f"  ▶ Phase 4 Complete: {len(demos)} multi-page commercial prototypes created.")
        return demos

    def run_outreach_step(
        self,
        ctx: BusinessCycleContext,
        demos: Sequence[DemoRecord],
        **kwargs: Any,
    ) -> List[OutreachRecord]:
        """Generate personalized outreach variants and place them in the approval queue."""
        print(f"\n✉️ [PHASE 5: PERSONALIZED AI OUTREACH DRAFTING] Drafting email copy for {len(demos)} prototypes...")
        drafts: List[OutreachRecord] = []
        for idx, demo in enumerate(demos, 1):
            business = self.db.get_business(demo.business_id)
            opp = self.db.get_opportunity(demo.opportunity_id)
            research = self.db.get_business_research(demo.business_id)
            if business is None or opp is None:
                continue
            variants = self.outreach_generator.generate(business, opp, demo, research)
            for record in self.outreach_generator.to_records(business, opp, demo, variants[: self.variants]):
                qa = self.quality_outreach.check(record)
                if not qa.passed:
                    ctx.errors.append(
                        f"outreach quality gate failed for {record.id}: {qa.issues} | {qa.warnings}")
                    continue
                self.db.save_outreach(record)
                drafts.append(record)
                self.db.update_business_status(business.id, BusinessStatus.OUTREACH_READY)
                print(f"  [{idx}/{len(demos)}] {business.name} -> Outreach Email Drafted!")
                print(f"     ├─ Recipient: {record.recipient_email}")
                print(f"     ├─ Subject: {record.subject}")
                print(f"     └─ Status: {record.approval_status.value} (Placed in Approval Queue)")
        ctx.outreach_drafts.extend(drafts)
        ctx.stats["outreach_drafts"] = len(drafts)
        print(f"  ▶ Phase 5 Complete: {len(drafts)} email drafts created.")
        print("\n" + "=" * 80)
        print(f"🎉 PIPELINE CYCLE COMPLETE — {len(drafts)} Opportunities Ready in Approval Studio!")
        print("👉 Open Dashboard: http://127.0.0.1:8585")
        print("=" * 80 + "\n")
        return drafts

    def run_response_tracking_step(
        self,
        ctx: BusinessCycleContext,
        **kwargs: Any,
    ) -> List[OutreachResponse]:
        """Classify any inbound responses staged on the context (Jim's ingestion
        feeds raw responses via :meth:`ingest_response`; this step also picks up
        anything left on ``ctx`` under ``pending_responses``)."""
        ingested: List[OutreachResponse] = []
        pending = getattr(ctx, "pending_responses", []) or []
        for item in pending:
            outreach_id = item.get("outreach_id")
            raw = item.get("raw_content") or item.get("message")
            if not outreach_id or not raw:
                continue
            record = self.ingest_response(ctx, outreach_id, raw)
            if record:
                ingested.append(record)
        ctx.responses_processed.extend(ingested)
        ctx.stats["responses_processed"] = len(ingested)
        return ingested

    # -- targeted entry points --------------------------------------------
    def ingest_response(self, ctx: Optional[BusinessCycleContext], outreach_id: str,
                        raw_content: str) -> Optional[OutreachResponse]:
        """Classify one inbound reply and persist it PENDING_REVIEW."""
        outreach = self.db.get_outreach(outreach_id)
        if outreach is None:
            raise ValueError(f"Unknown outreach id: {outreach_id}")
        classified = self.classifier.classify_records(outreach, raw_content)
        response = OutreachResponse(
            id=f"resp_{classified.outreach_id[:10]}",
            outreach_id=outreach.id,
            business_id=outreach.business_id,
            classification=classified.classification,
            raw_content=raw_content,
            suggested_reply=classified.suggested_reply,
            reply_status=ReplyStatus.PENDING_REVIEW,
        )
        self.db.save_outreach_response(response)
        self.db.update_business_status(outreach.business_id, BusinessStatus.REPLIED)

        # Auto-suppress any pending/approved follow-ups on opt-out or wrong-contact
        if classified.classification in (
            ResponseClassification.UNSUBSCRIBED,
            ResponseClassification.WRONG_CONTACT,
            ResponseClassification.NOT_INTERESTED,
        ) or getattr(classified, "suppression_signal", False):
            for fu in self.db.list_followups(outreach_id=outreach.id):
                if fu.status in (FollowUpStatus.PENDING_REVIEW, FollowUpStatus.APPROVED):
                    self.db.update_followup_status(fu.id, FollowUpStatus.SUPPRESSED)

        if ctx is not None:
            ctx.responses_processed.append(response)
        return response

    # -- follow-up & feedback (extra steps for Jim's cycle) --------------
    def followup_step(
        self,
        ctx: BusinessCycleContext,
        policy: Optional[FollowUpPolicy] = None,
        today: Optional[Any] = None,
    ) -> Tuple[List[FollowUpRecord], List[FollowUpPlan]]:
        policy = policy or self.followup_policy
        staged, plans = self.followup.plan_and_stage(self.db, policy, today)
        ctx.stats["followups_staged"] = len(staged)
        ctx.stats["followups_eligible_plans"] = len([p for p in plans if p.eligible])
        return staged, plans

    def feedback_step(self, ctx: BusinessCycleContext) -> FeedbackReport:
        report = self.feedback.learn(self.db)
        ctx.stats["feedback"] = report.api_dict()
        return report

    # -- helpers ----------------------------------------------------------
    def _persist_opportunity(self, scored: ScoredOpportunity) -> OpportunityRecord:
        opp = OpportunityRecord(
            id=f"opp_{scored.business_id[:20]}",
            business_id=scored.business_id,
            opportunity_type=scored.opportunity_type or OpportunityType.LEAD_CAPTURE,
            title=scored.title,
            problem_summary=scored.problem_summary,
            proposed_solution=scored.proposed_solution,
            business_value=scored.business_value,
            score=scored.score,
            score_reasons=scored.score_reasons,
            risks=scored.risks,
            confidence=scored.confidence,
            priority=scored.priority,
            qualification_status=scored.qualification_status,
            evidence_ids=scored.evidence_ids,
            status="scored",
        )
        return self.db.save_opportunity(opp)

    # -- legacy ABC steps that belong to Jim's infra (delegated or no-op) --
    def run_discovery_step(self, ctx: BusinessCycleContext, *, limit: int = 10, **kwargs: Any) -> List[BusinessRecord]:
        from b2b.discovery import DiscoveryService
        service = DiscoveryService(db=self.db)
        return service.ingest_leads(provider_name=kwargs.pop("provider", "csv"), limit=limit, **kwargs).businesses

    def run_research_step(self, ctx: BusinessCycleContext, businesses: Sequence[BusinessRecord]) -> List[BusinessResearch]:
        provider = kwargs_research_provider()
        if provider is None:
            ctx.errors.append("No research provider configured; run_research_step skipped (Jim owns live fetch).")
            return []
        results = []
        for biz in businesses:
            research = provider.research(biz)
            self.db.save_business(biz)
            self.db.save_business_research(research)
            self.db.update_business_status(biz.id, BusinessStatus.RESEARCHED)
            results.append(research)
            ctx.researched.append(research)
        return results

    # -- analysis-only helpers (for tooling/tests) ------------------------
    def analyze_one(self, business: BusinessRecord, research: BusinessResearch) -> AnalysisResult:
        return self.analyst.analyze(business, research)

    def score_one(self, business: BusinessRecord, research: BusinessResearch) -> Optional[ScoredOpportunity]:
        result = self.analyst.analyze(business, research)
        return self.scorer.score(result, business, research)


def kwargs_research_provider():
    """Return a registered research provider or None (see b2b.research registry)."""
    try:
        from b2b.research import ResearchRegistry
        providers = ResearchRegistry.list_providers()
        if providers:
            return ResearchRegistry.get(sorted(providers)[0])
    except Exception:
        pass
    return None