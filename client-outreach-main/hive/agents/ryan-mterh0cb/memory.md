# Memory — Ryan (ryan-mterh0cb)

_Append durable facts, decisions, and context below._

## 2026-08-30 — Warm-up check
- Boot check: inbox empty, board empty, tasks.json has no tasks. Nothing dispatched to me yet.
- Hive root: `C:\Users\tirth\Desktop\automation\hive`; my workspace `agents/ryan-mterh0cb`.
- Running build: Munder Difflin v0.4.6 (that is what to quote if asked which build is live).

## 2026-08-30 — Phase 8 verification: BLOCKED (FFmpeg missing)
- Ran `python src/cli.py doctor`: **FFmpeg Core MISSING** (doctor suggests `winget install Gyan.FFmpeg`).
- Also noted: edge-tts not installed (ERROR), SQLite OK (4 jobs), YouTube Shorts and Instagram Reels staged-only (no tokens). Target canvas 1080x1920 9:16.
- Per dispatch instructions: do NOT install FFmpeg without authorization; stop at the blocker and report.
- Did NOT run `auto --limit 1` or `pytest tests -q` — both gated on the MP4 render path needing FFmpeg.
- Sent Phase 8 blocker report to Jim (jim-mtel249y) via outbox. Suggested fix: authorize `winget install Gyan.FFmpeg`, or operator approves install.
- Python 3.10.8 on PATH. Repo cwd: C:\Users\tirth\Desktop\automation (src/cli.py present, works).

## 2026-08-30 — Phase 8 verification: PASS (unblocked & fixed) → reported to Jim
- Authorization granted to fix blockers. Actions taken:
  1. FFmpeg already present via winget (Gyan.FFmpeg 9.0.1) but NOT on PATH and its WinGet dir is versioned (`Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe`) so `find_ffmpeg()`'s `Packages/Gyan.FFmpeg` glob missed it. Fixed by persisting the bin dir on user PATH AND creating a junction `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg` → versioned package dir (app glob finds it; verified via `find_ffmpeg()` / doctor OK).
  2. edge-tts 7.2.8 ALREADY in `.venv` — no install; doctor Edge-TTS OK when run with `.venv\Scripts\python.exe` (system python on PATH lacks it, which caused the earlier ERROR).
- Blocked the render twice with real bugs in `src/video/compositor.py` (build v0.4.6):
  1. concat output `[vg]` left unconnected when scenes-mode chain had `,ass=…` appended after the labeled pad.
  2. Fix: caption/header ASS chain must bind DIRECTLY onto the pad link (no comma) — `;[vg]` + ass chain re-entry, no `,[vg],` forms. Also unified non-scenes path (`[0:v]ass=…` not `[0:v],ass=…`). Validated with direct ffmpeg filtergraph tests.
- Final render PASSED: `python src/cli.py auto --limit 1` → `output\final\trump-blacklisting-of-woke-anthropic-deemed-illegal-by-feder.mp4`
  - 1080x1920 (9:16), h264, 30fps, duration 20.27s (audio AAC 44.1kHz stereo 20.25s — in sync), size 890,948 bytes (~870 KB), bitrate ~351.7 kb/s.
  - Burned captions verified: bright text pixels (YMAX 231–253) in caption band at y≈1300–1650; scene-header band y 0–400 has text too.
  - Multi-scene verified: 4 header segments (HOOK/SETUP/POINT/CTA) + differing third-scene color (signalstats YAVG/UAVG/VAVG distinct at t=17s).
  - QA score 96.0/100 PASSED; thumbnail + publish metadata + scripts + SRT/ASS all produced.
  - BGM ducking: configured (music.enabled:true, ducking:true) but NOT exercised — `assets/music` empty, so `has_bgm=False`; loudnorm (-14 LUFS) applied to voice. Reported as limitation.
- Tests: `python -m pytest tests -q` → **95 passed, 1 skipped** (skip = `test_video_engine.py:23` FFmpeg-absent negative path, now genuinely N/A since FFmpeg present).
- Environment note: `python` on PATH = system 3.10.8. Always use `.venv\Scripts\python.exe` for this project (edge-tts/pytest live there).
- Do NOT start Phase 9 (per dispatch). Sent completion report to Jim (jim-mtel249y).

## 2026-08-30 — Phase 8 verification re-run: PASS (BGM ducking now exercised)
- Re-dispatched task; re-ran full verification with `.venv\Scripts\python.exe`. Confirmed everything still green.
- doctor: FFmpeg OK, Edge-TTS OK, SQLite OK (now 8 jobs indexed; Reddit still 403-blocked). 
- `auto --limit 1` picked a NEW ungenerated item (earlier shorts are marked generated/skipped): "Apple One and Apple TV subscription prices increase by up to 20 percent" (Ars Technica, score 48).
- THIS run exercised **BGM ducking** for the first time: `INFO voice.audio_mixer: Mixing background music: ambient_lofi.mp3 (vol=0.12, duck=True, loudnorm=True)` — a music track now exists in assets/music.
- Live output: `output\final\apple-one-and-apple-tv-subscription-prices-increase-by-up-to.mp4`
  - ffprobe: 1080x1920 (9:16) h264 @30fps; video 21.87s; audio AAC 44.1kHz stereo 21.85s (in sync); size 892,947 bytes (~872 KB, bitrate ~326.7 kb/s).
  - Captions burned: YMAX=251 in caption band y1300-1650 @4s. Scene headers burned: YMAX=231 top band; 4 segments (HOOK/SETUP/POINT/CTA 0-2.97-10.89-18.81-21.78).
  - Multi-scene colors distinct: mid-band @2s (Y39/U137/V118) vs @14s (Y48/U140/V116).
  - QA score 96.0/100 (PASSED).
- Generated artifacts (all under `output/`): mp4 892,947 B; thumb.jpg 56,452 B; meta.json 8,028 B; publish.json 2,083 B; audio mp3 135,936 B (21.79s TTS); script json 6,027 B; drafts: .ass 7,476 B, headers.ass 783 B, .srt 656 B, timings.json 4,946 B.
- pytest: `95 passed, 1 skipped` (skip remains the FFmpeg-absent negative path, legitimately N/A). Runtime ~6s.
- Remaining blockers: NONE for Phase 8. Platform uploads still staged-only (no tokens) by design. Not starting Phase 9.
- Session note: earlier breaker "steer" messages (repeated bash/read) were stale artifacts of Phase 8 debugging; acknowledged to god as resolved. No active loops.

## 2026-08-30 - Phase 9: Performance Analytics Intelligence layer COMPLETE -> reported to Jim
- Inbox at start: Jim (jim-mtel249y) informed me the Phase 9 Analytics Infrastructure API was live (src/analytics/{models,reporter,collector}.py, performance_snapshots table, sync-metrics/analytics/analytics-summary CLI, 103 pytest green). Two breaker messages (19-52/19-53) fired during my read-heavy exploration (28x read) - acked to god as resolved, moved to .done.
- BUILT the AI feedback loop on top of Jim's infra (all additive / opt-in / default OFF; nothing replaced):
  1. src/analytics/models.py += MetricAggregate, InsightFinding, InsightsReport.
  2. src/analytics/insights.py (NEW) PerformanceInsightsEngine: correlates engagement across 8 dims (content_format, hook_strategy, target_audience, topic_pattern, scene_count, target_duration, cta_strategy, platform; scene/duration/CTA from strategy_json), interpretable recommendations w/ confidence + reliable flag, get_feedback_multipliers() (0.6-1.5, min_samples guard => neutral 1.0), best_feedback_boost() (+/- pts on strongest signal).
  3. src/analytics/feedback.py (NEW) PerformanceFeedbackScorer: classifies candidate via its ContentStrategy, additive bounded explains. score()/explain()/rerank(); no-op when no signal.
  4. ContentSelector.select_candidates(..., feedback_scorer=) - optional additive re-rank; `auto --feedback` or config analytics.feedback_enabled (DEFAULT false) in config.yaml analytics:{feedback_enabled,min_samples,max_score_adjustment}.
  5. TopicStrategist(config, performance_feedback=True, feedback_db=) - opt-in potential-score nudge + notes; heuristic path untouched when off.
  6. CLI: `python src/cli.py intelligence [--platform] [--min-samples]`; Dashboard GET /api/analytics/insights.
- Verification: full suite 113 passed, 1 skipped (was 103; +10 new tests: test_analytics_insights.py, test_analytics_feedback.py + CLI/dashboard additions; single skip still the legitimately N/A FFmpeg-absent test). Live `intelligence` on automation.db: 9 jobs / 5 snapshots - correlates all 8 dims; no top recommendations yet (history explainer-heavy, near-benchmark) - correct at this sample size.
- Sent phase9-complete-to-jim.json (outbox) + breaker-ack-f0963b-e74cbb-to-god.json. Inbox empty. Next: Phase 10 when dispatched.

## 2026-08-30 - Phase 10: Productionization & Long-Running Automation (Ryan slice) COMPLETE -> reported to Jim
- Jim dispatched Phase 10 with ownership split (Jim: reliability/scheduling/publishing/analytics-collection/observability/safeguards; Ryan: content-quality optimization, diversity, performance analysis, feedback-strategy refinement) + sent interface-proposal inbox msg (20-04) with my 3 proposed items. I replied outbox phase10-interface-align-to-jim.json (agreed, listed deliverables, 3 interface requests). Jim had ALREADY wired analytics.factory.build_selection_scorer into scheduler/runner.py run_cycle (config-gated, fallback PerformanceFeedbackScorer) - contract live.
- BUILT (all additive / opt-in / default OFF; nothing replaced; publishing untouched/safety-gated):
  1. src/analytics/insights.py hardened guards: min_jobs (default 2, distinct-job) + min_effect (default 0.10 effect-size floor) before any non-neutral multiplier/boost; new 9th dimension quality_band (bucket_quality); new combined_feedback_boost() opt-in multi-dim bounded mode (default mode still Phase 9 best_feedback_boost).
  2. src/analytics/diversity.py (NEW) DiversityScorer: topic near-duplicate (token Jaccard >= 0.35) + category fatigue (>=2 of last 6 jobs) penalties, bounded by max_diversity_penalty 5.0, stateless from DB job history.
  3. src/analytics/factory.py (NEW) SelectionScorer composite + build_selection_scorer(db, config) + SelectionLedger (output/analytics/selection_ledger.jsonl). Returns None when disabled/no signal => raw ranking preserved.
  4. src/strategy/rotation.py (NEW) TemplateRotation: 4 deterministic visual variants, persisted output/analytics/rotation_state.json, never repeats last tag across restarts. Wired via TopicStrategist.develop_strategy(advance_rotation=True) ONLY on generation path (generators/bridge.py) so scoring passes never consume turns; config strategy.diversity_rotation (default false).
  5. src/cli.py: auto --diversity flag; cmd_auto builds composite scorer via factory when feedback/diversity enabled (config or flag), prints reasons, writes ledger. Parser + analytics/__init__ + strategy/__init__ exports updated.
  6. config/config.yaml: strategy.diversity_rotation; analytics.{feedback_enabled,diversity_enabled,min_samples,min_jobs,min_effect,max_score_adjustment,diversity_window,diversity_topic_similarity,diversity_topic_penalty,diversity_fatigue_threshold,diversity_fatigue_penalty,max_diversity_penalty}.
- VERIFICATION: new tests tests/test_analytics_diversity.py (6), tests/test_analytics_guardrails.py (4), tests/test_rotation.py (5), + parser assertions in test_analytics_cli.py. FULL SUITE: 135 passed, 1 skipped (baseline 113 + my 15; skip remains legit N/A FFmpeg-absent negative-path test).
- LIVE verify on real automation.db (now 10 jobs / 10 snapshots): intelligence runs 9 dimensions; top_recommendations [] and composite scorer delta 0.0 with feedback+diversity enabled => NO manufactured recommendations from near-benchmark history (guardrails confirmed live); rotation advanced once (neon_kinetic, turns=1) with state persisted; ledger writes. Verified StoragePruningEngine targets ONLY audio/drafts/collected so output/analytics/ (rotation state + ledger) is never pruned.
- Sent phase10-complete-to-jim.json outbox. No blockers.

## 2026-08-30 - Inbox triage (post-Phase-10): all handled, inbox empty
- 8 pending msgs processed and moved to inbox/.done/: (1) Jim (jim-mtel249y) Phase 10 interface-proposal PROPOSE (20-04) - replied outbox phase10-interface-align (delivered, in .sent) + built deliverables; (2) Jim Phase 10 infrastructure-ready INFORM (20-08-16) - already built diversity/factory/rotation on that surface; (3-8) six breaker STEER/CONSTRAIN msgs (20-06..20-16: read x8 / edit x8 / edit x14 / bash x12) - stale artifacts of the rolled-up Phase 9/10 working session; loops resolved (full suite 135 passed/1 skipped, no active loop), so NO god message sent (per instruction: only message god when a decision is genuinely needed). Also a 9th msg (66d0bc, bash x12 steer) arrived mid-triage - same stale handling.
- Outbox confirmed consumed by relay (my phase10-interface-align + phase10-complete now in outbox/.sent/). No pending items remain.
- 20-08-30 inbox follow-up: breaker CONSTRAIN 20-17 (bash x20, conv-af42c5) - same stale batch from the phase9/10 working session, loop resolved, no god sign-off needed (nothing pending to authorize); moved to .done. 66d0bc confirmed already .done.

## 2026-08-30 - PIVOT: project direction changed (god directive)
- Product is NO LONGER Shorts/Reels automation. New product: Business Discovery -> Research -> AI Business Analyst -> Opportunity Score -> Personalized Demo -> Personalized Email -> Human Approval -> Email Sending -> Response Tracking -> Follow-ups.
- My lane: AI business analysis, opportunity ID/scoring, demo strategy/personalization, personalized outreach, response classification, follow-up intelligence, sales optimization.
- Constraints: no fabrication of business/performance data; do not modify automation/hive; coordinate interfaces with Jim before implementing; DO NOT implement yet.
- Produced phase11-architecture-proposal.md in my agent dir: reuse-as-is (analytics factory/ledger, insights guardrail engine, selector+history dedup, ranker breakdown pattern, quality gate pattern, safeguards quota/prune/health, scheduler daemon+rules, db/config layer, openai_generator LLM client), reuse-as-pattern (diversity fatigue, rotation variants, bucketing, AI/heuristic arbitration, snapshotting for response tracking), obsolete (generators script/template/director, video/, voice/, publishers/, reddit/rss collectors semantics, content-only DIMENSIONS).
- New domain: src/business/{analyst,opportunity,demo_strategy,outreach,response_insights,followups}.py + shared src/llm.py; new tests/test_business_*.
- Pending: Jim's architecture audit/roadmap (inbox empty as of now) - must coordinate interfaces (CompanyDossier contract, email send surface+human approval, response ingestion webhook, audit coverage, scheduler ownership) BEFORE implementing.

## 2026-08-30 - Jim ALIGN: Master Project Realignment (B2B Indian-business outreach)
- Read DEVELOPMENT_PLAN.md (12-phase roadmap A-L) + Jim align msg. My phases: D (AI Analyst 9 questions + 0-100 opportunity scorer), E content side (demo templates/verticals), F (personalized outreach copy incl. Day-3 follow-up), I (response classifier + suggested replies), K (feedback/conversion learning, Phase-10 guardrail gating).
- Jim: schema/tables (Phase A), discovery, research infra, demo hosting, approval gate + email sending, response ingest, daemon, dashboard.
- Non-negotiables: human approval first, zero fabrication (verified_fact/ai_inference/unknown -> UNKNOWN default), concrete-specific solves, real interactive prototypes, 135 tests stay green.
- Sent outbox phase11-align-to-jim.json locking 5 interface contracts: (1) ResearchEvidence read API, (2) DemoRecord artifact + vertical taxonomy, (3) OutreachRecord fields (I write copy+reasons+evidence, Jim gates/sends), (4) outreach_responses ingest (classification+reply as pending_review), (5) scheduler intent-layer library steps like Phase 10 scorer contract.
- Handled inbox: Jim align (replied) + breaker steer 8f94ea (read x24 - stale artifact of inspection turn, no live loop, no god msg) -> both .done. Inbox empty.
## 2026-08-30 - MASTER RESET: Client Outreach Automation - Ryan slice in progress
- Full reset directive received (god/user): ONLY product is AI-Powered Client Outreach/Business Acquisition for Indian SMBs. Old video/Shorts stack = legacy, don't build on it. AVAILABLE INFRA (Jim, Phase A done, 151 passed/1 skipped): b2b/models.py (BusinessRecord, ResearchEvidence, BusinessResearch, OpportunityRecord [score 0-100 + score_reasons], DemoRecord [vertical+type+artifact_path output/demos/<id>/index.html], OutreachRecord [personalization_reasons, evidence_used, followup_body, approval_status, send_status], OutreachResponse [classification+suggested_reply+reply_status], all state enums), db/database.py (full CRUD, 7 b2b tables, indexes), discovery.py (CSV+Manual providers, Deduplicator, DiscoveryService; cli 'discover'/'leads'), research.py (EvidenceCollector + BaseResearchProvider interface ONLY, no concrete provider, no network fetch yet), gatekeeper.py (approval gate), scheduler_intent.py (BusinessPipelineIntent ABC with run_analysis/demo/outreach/response_tracking steps + BusinessCycleContext).
- NOT yet built (Jim's lane): concrete ResearchProvider (Phase C fetch), EmailProvider/console send (Phase H), dashboard b2b UI/API (Phase G), scheduler b2b wiring, followups table, suppression entity, response ingest webhook.
- GAPS in contracts relevant to me: ResponseClassification has NO UNSUBSCRIBED/WRONG_CONTACT; no Followup entity/table; no suppression concept. Must coordinate (schema is Jim's).
- MY SLICE (per reset + DEVELOPMENT_PLAN sec 5): AI Analyst (Phase D, 7 Qs + insufficient_evidence) - Opportunity Scorer (0-100 transparent dims, confidence separate, no fake precision) - Demo strategy+generation (Phase E, real interactive HTML in output/demos) - Personalized outreach (Phase F, traceable evidence, variants, day-3 followup) - Response classifier + suggested reply (Phase I) - FollowUp intelligence (Phase J, day0/3/7, suppression+approval respect) - feedback/conversion learning (Phase K, min-samples neutral) - quality evaluation.
- PLAN: implement BusinessPipelineIntent concretely as ONE bundle (b2b/pipeline.py) so Jim can wire his scheduler; coord msg to Jim (in outbox) asking for suppression enum + followup persistence contract. E2E research input: use seeded/offline research fixtures (no live fetch provider yet - Jim's), be explicit what is real vs canned.


## 2026-08-30 - Phase D/E/F/I/J/K bundle IMPLEMENTED + green (Ryan slice)
- Jim had ALREADY added both of my coord asks: ResponseClassification += UNSUBSCRIBED/WRONG_CONTACT; FollowUpRecord + FollowUpStatus + followups table + CRUD (save/get/list/update_followup_status). My outbox coord msg already delivered (.sent).
- Built/exported in src/b2b/ (aligned to real locked models, not my earlier guesses):
  - analyst.py (BusinessAnalyst, AnalysisResult, vertical_for, insufficient_evidence gate, 7-question grounding, evidence-only hypotheses)
  - scoring.py (OpportunityScorer: 8 transparent dims summing to 100, ScoredOpportunity, confidence SEPARATE from score, neutral midpoint, priority+qualification)
  - demo_generator.py (DemoStrategy/DemoGenerator: self-contained interactive HTML prototypes under output/demos/<id>/index.html, @TOKEN@ substitution, vertical accents)
  - outreach.py (OutreachGenerator: variants, personalization_reasons, evidence_used, followup_body, PENDING_REVIEW records)
  - response_classifier.py (ResponseClassifier: keyword rules -> ResponseClassification incl UNSUBSCRIBED/WRONG_CONTACT, suppression_signal, disputed, suggested_reply)
  - followup.py (FollowUpIntelligence/FollowUpPolicy/FollowUpPlan: day 0/3/7 cadence, terminal-response + suppression suppression, stages REAL FollowUpRecord PENDING_REVIEW via db.save_followup, dedup + max cap)
  - feedback.py (OutreachFeedbackEngine: OutcomeSample/DimensionFinding/FeedbackReport, min_samples=5 + min_effect linearity, neutral-when-sparse)
  - quality.py (OutreachQualityChecker/DemoQualityChecker: traceability + no-fabrication + no-placeholder)
  - pipeline.py (BusinessIntelligenceService implementing BusinessPipelineIntent: run_analysis/demo/outreach/response_tracking step + ingest_response + followup_step + feedback_step; reads optional config "b2b" section; lazy import of db.database to break the db.database<->b2b.models<->b2b init cycle)
  - fixtures.py (StaticResearchProvider registered "static_sample", SAMPLE_BUSINESSES, build_sample_business_dataset, generate_sample_research; negative case = empty evidence)
  - b2b/__init__.py exports updated (64 names); cli.py += `business-cycle` command (--demo seeds fixtures, --json report).
- TESTS: new tests/test_b2b_intelligence.py (20 tests: analyst gate, scorer transparency/neutral, demo artifacts + quality, outreach traceability+pending, classifier signals/suggestions, follow-up due/dedup/suppression/max, feedback neutral-then-recommend, pipeline round-trip). Full suite 180 passed / 1 skipped.
- Verified E2E offline: 5-6 fixture businesses -> scored opps -> 5-6 demos (real HTML in output/demos) -> 10-12 outreach drafts PENDING_REVIEW. Seeded output/automation.db (shared dev DB, has Jim 21 leads + fixtures) via `python src/cli.py business-cycle --demo --output-dir output`.
- Next: Jim reply on dashboard/scheduler b2b surface + EmailProvider timing; my followup.py now uses his FollowUpRecord table so nothing pending on my side except E2E acceptance (dashboard URL + provider send) which is Jim?s lane.


## 2026-08-30 - Inbox sweep: Jim agree/inform + 10 stale breaker msgs handled
- Jim agree (ced1c7): confirmed UNSUBSCRIBED/WRONG_CONTACT + followups table+CRUD live, approves my pipeline bundle, in progress on Phase C scraper + email sending + dashboard lead studio. Jim Phase B inform (fd4f76): discovery engine + 20-lead CSV + discover/leads/add-lead CLI, 159 tests. Both info -> .done.
- 10 breaker steer/constrain msgs (6613be, b71b03, 0c8c0b, 5a6cf4, e141a4, 548411, ecdc88, 47a3a5, 0249fb, 69fd7d): stale artifacts, heuristic fired on my long completed build turn (massed reads/edits/bash) + my batch inbox read. NOT looping. Sent ONE consolidated ack to god (breaker-ack-09-51-stale-build-turn-to-god.json) with summary + short plan (read-only; await Jim dashboard/email providers; then wire views + approve->send->ingest E2E). All moved to inbox/.done/. Inbox empty.
