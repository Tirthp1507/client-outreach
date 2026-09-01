# Phase 11 — Business Discovery & Personalized Outreach: Architecture Proposal (Ryan)

Status: PROPOSAL (no implementation). Awaits Jim's architecture audit/roadmap (not yet in inbox) for interface coordination.

---

## 1. Product Direction

New product: **Business Discovery → Research → AI Analyst → Opportunity Score → Personalized Demo → Personalized Email → Human Approval → Email Sending → Response Tracking → Follow-ups.**

Shorts/Reels automation is no longer the product. Ryan owns the intelligence layer:
AI business analysis, opportunity identification/scoring, demo strategy & personalization,
personalized outreach, response classification, follow-up intelligence, sales optimization.

Non-negotiable constraints (carried forward): no fabricated business/performance data;
do not modify automation/hive; coordinate interfaces with Jim before implementation.

---

## 2. Reusable vs Obsolete Inventory (grounded in current `src/`)

### 2.1 Reuse-as-is (drop-in)
| Component | File(s) | Why reusable |
|---|---|---|
| AI/strategy logic | `strategy/topic_strategist.py` (heuristic + AI provider + bounded additive adjust + notes trail) | The **pattern** applies to demo strategy; content-specific rules get replaced |
| Additive scorer factory + audit ledger | `analytics/factory.py` (`SelectionScorer`, `SelectionLedger`, `build_selection_scorer`) | Composite scoring + why-rationale ledger transfer whole to opportunity/outreach re-ranking |
| Statistical guardrail engine | `analytics/insights.py` (min_samples / min_jobs / min_effect / ratio-vs-benchmark / reliable flag) | The exact "don't manufacture signals" discipline; re-point dimensions at business outcomes |
| Feedback multipliers | `analytics/insights.get_feedback_multipliers` + `analytics/feedback.py` | Learned nudge machinery reusable AFTER real response data accrues; stays neutral until then |
| Candidate selection + history dedup | `pipeline/selector.py`, `pipeline/history.py` (`ContentSelector`, `HistoryStore`) | Filter-by-threshold + dedup-by-URL/topic ≡ don't re-contact same company/contact |
| Scoring-with-breakdown pattern | `processors/ranker.py` (`ContentRanker`) | Weighted 0-100 + breakdown dict + reasons list → template for OpportunityScorer |
| QA-gate pattern | `pipeline/quality.py` (`QualityValidator`, `QualityReport`, PASS/WARN/FAIL) | Re-skin into `OutreachQualityValidator` (placeholder-check, spam-signal, personalization proof) |
| Operational safeguards | `pipeline/safeguards.py` (`PublishQuotaGuard`→send-count guard, `StoragePruningEngine`, `SystemHealthMonitor`) | Publishing quota pattern maps 1:1 to daily outbound-cadence cap; pruning + health as-is |
| Daemon / orchestration skeleton | `scheduler/daemon.py`, `scheduler/runner.py`, `AuditLogRecord`/`audit_logs` | Long-running cycle + audit log survives whole; inner steps swap content→campaign |
| SQLite layer + config | `db/database.py`, `config.py`, `config/config.yaml` | Table/migration pattern, snapshot pattern, config layering reuse directly |
| LLM client | `generators/openai_generator.py` (endpoint-agnostic `/chat/completions`, JSON extraction, credential hygiene) | Reuse (likely lift to a shared `llm` client) for analyst/email/demo calls |

### 2.2 Reuse-as-pattern (concept ported, implementation new)
| Concept | Source | Port target |
|---|---|---|
| Anti-repetition / fatigue | `analytics/diversity.py` (`DiversityScorer`) | Delivery-angle fatigue & demo variety across accounts/sequence |
| Variant rotation | `strategy/rotation.py` (`TemplateRotation`, persisted state) | Message/template rotation so the same company never sees identical copy |
| Topic-pattern / bucketing classifiers | `insights` (quality_band, topic_pattern, buckets) | Business signals bucketing (firmographics, tech signals, urgency) |
| AI vs heuristic provider arbitration | `topic_strategist.develop_strategy` | Business Analyst / demo strategy: LLM first, heuristic fallback, no partial output |
| Metrics snapshotting | `analytics/collector.py` + `PerformanceSnapshot` | Response tracking: each reply/email open becomes a snapshotted event |

### 2.3 Obsolete for the new product (do not port; leave untouched, not deleted)
| Area | Reason |
|---|---|
| `generators/` script/template/strategy_director + `ShortScript` | Video narration pipeline is not the product |
| `video/` (compositor, broll, ffmpeg_utils) | Shorts rendering not needed |
| `voice/` (TTS, audio_mixer, subtitle_aligner) | No narration |
| `publishers/` youtube/instagram (publisher, metadata_generator) | No social publishing; superseded by email-sending surface (Jim) |
| `collectors/reddit_collector.py`, `rss_collector.py` (feed semantics) | Discovery source ≠ RSS/Reddit content; RSS *transport* could later feed company-news signals (optional) |
| Content-specific `insights.DIMENSIONS` (hook/format/cta/half of scene metrics) | Entertainment dimensions replaced by business-decision dimensions |

Test suite: content/video tests stay green but are now regression-only; new `tests/test_business_*` added for the new layer.

---

## 3. Proposed Architecture (Ryan scope)

Reuses the orchestrator skeleton (`scheduler/runner` style) with a new domain package `src/business/`
plus a shared `src/llm.py` client lifted from `generators/openai_generator.py`.

### 3.1 Business Analyst — `src/business/analyst.py`
- Input: normalized **CompanyDossier** (website, news, hiring signals, tech-stack/founder/ICP evidence collected by Jim's discovery/research infra).
- Output: structured `BusinessProfile { sector, size, segment, buying_signals[], pains_inferred, urgency, evidence: {field: [url]} }`.
- Rules: **every field requires `evidence`**; a field with no evidence stays `null`/`unknown` (no fabrication, per constraint). Confidence per field; heuristic fallback mirroring `TopicStrategist`.

### 3.2 Opportunity Scoring — `src/business/opportunity.py`
- `OpportunityScorer`: weighted factor model (fit, urgency, budget/intent signals, recency, channel) → 0-100 **with breakdown + reasons** (ported from `ContentRanker` componentization), composed via `build_selection_scorer`-style factory so it is *additive and removable*.
- Guardrails (reuse `insights` discipline): no `has_signal` → not surfaced; scores only when enough distinct evidence; no learned multipliers until real outbound data exists.

### 3.3 Demo Strategy — `src/business/demo_strategy.py`
- Port of `TopicStrategist` pattern: `develop_demo_strategy(profile, product, advance_rotation)` → `DemoPlan { angle, value_prop, proof_points, objections, cta }`, AI-first with heuristic fallback.
- Reuses `TemplateRotation` for angle/template variety; reuses fatigue reasoning (don't re-send same angle to same account).

### 3.4 Personalized Email Generation — `src/business/outreach.py`
- `PersonalizedEmailBuilder`: rule scaffold + LLM fill, bound to evidence only.
- Mandatory `OutreachQualityValidator` gate: PASS/WARN/FAIL — no leftover placeholders, unique factual hook per recipient, no false guarantees, length/sender hygiene. Output staged for **human approval** (never auto-send).

### 3.5 Response Classification — `src/business/response_insights.py`
- `Classifier`: deterministic router (keywords) + LLM fallback → taxonomy `{positive, question, not_now, out_of_office, unsubscribe, angry, no_reply}` with confidence; stored as snapshotted `ResponseRecord` (reuse `PerformanceSnapshot` persistence pattern).
- Feeds scoring multipliers + follow-up intelligence only after real labeled volume passes guardrails.

### 3.6 Follow-up Recommendations — `src/business/followups.py`
- Reuses `insights` correlation engine on **real** outbound history: which angle/timing/CTA correlates with positive replies — gated by min_samples/min_jobs/min_effect so nothing is claimed cold.
- Until sufficient data: deterministic cadence rule (no learned claims), per-account variant rotation to avoid identical sequences.

### 3.7 Data model (extend existing SQLite, same conventions)
`companies`, `contacts`, `opportunities`, `outbound_emails` (state machine staged/approved/sent), `responses`, `followup_schedule`; reuse `audit_logs` + `SelectionLedger`-style rationale ledger for full observability. Publish-quota pattern → `SendQuotaGuard`.

---

## 4. Interface coordination with Jim (pending his audit/roadmap)
1. **CompanyDossier contract**: I consume discovery/research output in a normalized shape — need Jim to confirm source/fields.
2. **Email send surface**: Jim owns sending infrastructure + approval-flag enforcement (mirror of Phase 7 staged publishing); I produce staged outbound email records + QA report, never send.
3. **Response ingestion**: inbound reply webhook (Jim) → normalized `ResponseRecord` I classify.
4. **Observability**: my modules write to `audit_logs` + feature ledger so `/api/audit` covers campaigns end-to-end.
5. **Scheduling/daemon**: Jim owns scheduling/reliability; I contribute domain cycles (intelligence passes) as library steps, as in Phase 10.

No implementation yet — this proposal is for review and to unblock Jim's interface feedback.