# B2B CLIENT OUTREACH AUTOMATION — MASTER PROJECT DOCUMENTATION

```
CURRENT STATUS:               COMPLETE & PRODUCTION-STAGED (100% Green Test Suite)
CURRENT DASHBOARD URL:        http://127.0.0.1:8088
CURRENT BRANCH/WORKING STATE: master / clean working tree
LAST VERIFIED:                2026-08-30
TEST STATUS:                  189 passed, 1 skipped (0 failures across 46 modules)
EMAIL MODE:                   MOCK / DRY-RUN (Safe Audit Mode) [Toggleable to REAL EMAIL]
MOST IMPORTANT REMAINING WORK:Configure production SMTP credentials for live prospect sending; connect CRM webhook exports.
```

## If you are an AI agent starting work
1. **Read this README completely** before touching any files.
2. **Inspect the repository structure** and cross-check the referenced source files.
3. **Verify the current status against actual code** — never assume behavior if runtime contradicts it.
4. **Before making changes**, identify the affected architecture components and respect the non-negotiable safety rules.
5. **Run tests after changes** (`python -m pytest`).
6. **Update this README** if architecture, database schema, or project status changes materially.

---

# 1. EXECUTIVE SUMMARY

### What This Project Does
The **Automated AI B2B Client Outreach System** is an end-to-end client acquisition engine designed for software agencies, consultants, and B2B service providers targeting local businesses (initially focused on Indian SMBs across healthcare, salons, restaurants, coaching academies, retail, and professional services).

### Who the User Is
Sales development representatives (SDRs), agency owners, and growth marketers who need to discover prospect businesses, audit their digital presence, calculate commercial opportunity, generate tailored interactive prototype demonstrations, synthesize personalized outreach emails, review & approve outreach through a dedicated dashboard, safely send communications, classify inbound responses, manage follow-up cadences, and learn from conversion signals.

### What Problem It Solves
Traditional B2B cold outreach suffers from low response rates (1–2%) because emails are generic, boilerplate, and unconvincing. Local business owners ignore text pitches. This system solves that by:
1. Identifying exact operational gaps (e.g., phone-only bookings, missing online ordering, unoptimized mobile UX).
2. Generating a **custom, working, interactive HTML/JS prototype** branded for that specific business demonstrating the exact proposed solution.
3. Drafting personalized outreach citing specific verified facts and providing a live link to their tailored prototype.
4. Enforcing strict human approval before any email can be dispatched.

### Current Implementation State
- **Production-Ready / Complete**: SQLite schema (8 B2B tables), Indian lead discovery & deduplication, live HTTP web research engine, AI gap analysis & opportunity scoring, client-specific interactive prototype generator (8 vertical blueprints), outreach copy synthesizer with evidence provenance, human approval gatekeeper, email provider abstraction (Console dry-run & SMTP live), inbound multi-class response classifier, follow-up cadence manager with automated opt-out suppression, and full-featured B2B Lead Studio web dashboard.
- **Prototypes / Staged**: Interactive demo prototypes are standalone single-file applications generated in `output/demos/` designed for prospect presentation without backend server-side databases.
- **Mocked / Safe Defaults**: Console dry-run email provider is active by default to prevent accidental spam. Live SMTP delivery requires explicit configuration or test email overrides.

---

# 2. COMPLETE SYSTEM ARCHITECTURE

### Architecture Diagram

```
+----------------------------------------------------------------------------------------------------+
|                                    SCHEDULER & CLI INTERFACE                                       |
|                         (src/cli.py: discover, business-cycle, dashboard)                          |
+----------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
| 1. BUSINESS DISCOVERY & INGESTION (src/b2b/discovery.py)                                           |
|    - Sources: CSV files (data/indian_businesses_sample.csv), Manual entry, API registries           |
|    - Deduplication: Exact domain, normalized (name + city), token Jaccard similarity (>= 0.75)     |
|    - Persistence: 'businesses' table                                                               |
+----------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
| 2. DIGITAL PRESENCE RESEARCH ENGINE (src/b2b/research_engine.py, src/b2b/research.py)               |
|    - Engine: HTTPWebResearchProvider (safe rate-limited live audit, 10s timeout, custom User-Agent)  |
|    - Evidence Collector: Categorized claims (facts vs AI inferences vs unknowns)                   |
|    - Persistence: 'business_research' and 'research_evidence' tables                              |
+----------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
| 3. AI BUSINESS ANALYST & OPPORTUNITY SCORER (src/b2b/analyst.py, src/b2b/scoring.py)              |
|    - Analysis: 9 structured operational gap assessments across 8 verticals                         |
|    - Scoring: 0-100 explainable score based on verified gaps, digital readiness, commercial impact |
|    - Persistence: 'opportunities' table                                                            |
+----------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
| 4. CLIENT-SPECIFIC DEMO GENERATOR (src/b2b/demo_generator.py)                                      |
|    - Generator: Builds tailored, mobile-first, deeply interactive HTML/JS prototypes               |
|    - Blueprints: Clinic, Restaurant, Salon, Coaching, Gym, Retail, Real Estate, General SMB        |
|    - Artifacts: output/demos/<demo_id>/index.html                                                  |
|    - Persistence: 'demos' table                                                                    |
+----------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
| 5. PERSONALIZED OUTREACH GENERATOR (src/b2b/outreach.py)                                           |
|    - Synthesizer: Crafts email copy citing verified evidence, demo link, and follow-up sequence    |
|    - Status: DRAFT / PENDING_REVIEW                                                                |
|    - Persistence: 'outreach' table                                                                 |
+----------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
| 6. HUMAN APPROVAL & GATEKEEPER (src/b2b/gatekeeper.py)                                             |
|    - Verification: Mandatory check (approval_status == 'approved', recipient valid, copy present)  |
|    - UI: B2B Lead Studio ([Save Changes], [✓ Approve Draft], [✗ Reject])                           |
+----------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
| 7. EMAIL SENDING & SAFE AUDIT (src/b2b/email_provider.py)                                          |
|    - Modes: ConsoleEmailProvider (dry-run, writes output/outreach_staged/) vs SMTPEmailProvider    |
|    - Safety: Supports personal test recipient override for live verification                       |
|    - Persistence: Updates 'outreach' send_status, sent_at, provider_message_id                      |
+----------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
| 8. INBOUND RESPONSE & FOLLOW-UP CENTER (src/b2b/response_classifier.py, src/b2b/followup.py)       |
|    - Classification: 7 classes (interested, wants_meeting, wants_pricing, question,               |
|                      not_interested, unsubscribed, wrong_contact)                                  |
|    - Opt-Out Protection: UNSUBSCRIBED/WRONG_CONTACT automatically suppresses all future follow-ups |
|    - Cadence Manager: Stages Day 3 / Day 7 follow-ups into 'followups' table                       |
+----------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
| 9. SALES INTELLIGENCE & FEEDBACK LEARNING (src/b2b/feedback.py)                                    |
|    - Metrics: 8-stage conversion funnel (Discovered -> Researched -> Scored -> Demo -> Sent -> Won)|
|    - Conservative Learning: Multipliers require >= 5 real prospect outcomes before weight adjusting|
+----------------------------------------------------------------------------------------------------+
```

---

# 3. COMPLETE REPOSITORY MAP

```
automation/
├── data/
│   └── indian_businesses_sample.csv     # 20 real Indian SMB leads across 6 cities & 6 verticals
├── output/
│   ├── automation.db                    # Primary SQLite database
│   ├── demos/                           # Generated client-specific HTML/JS prototypes
│   └── outreach_staged/                 # Staged dry-run email JSON audit payloads
├── src/
│   ├── b2b/                             # CORE B2B CLIENT OUTREACH ENGINE
│   │   ├── __init__.py                  # Package exports
│   │   ├── analyst.py                   # AI Business Analyst (gap detection across 8 verticals)
│   │   ├── demo_generator.py            # Client-specific interactive prototype generator
│   │   ├── discovery.py                 # CSV and manual lead discovery + deduplication
│   │   ├── email_provider.py            # Console (dry-run) & SMTP email providers + sending service
│   │   ├── feedback.py                  # Conservative feedback optimization & learning engine
│   │   ├── fixtures.py                  # Seeded fixture data providers for testing
│   │   ├── followup.py                  # Multi-step cadence planner & opt-out suppression
│   │   ├── gatekeeper.py                # Human approval gatekeeper safety validator
│   │   ├── models.py                    # Core Pydantic models & state enums
│   │   ├── outreach.py                  # Personalized outreach copy generation
│   │   ├── pipeline.py                  # BusinessIntelligenceService master coordinator
│   │   ├── quality.py                   # Demo & outreach quality verification guards
│   │   ├── research.py                  # Evidence collector and base research interfaces
│   │   ├── research_engine.py           # Live HTTP rate-limited web presence scraper
│   │   ├── response_classifier.py       # Multi-class NLP response classifier & reply suggester
│   │   ├── scheduler_intent.py          # BusinessCycleContext intent state container
│   │   └── scoring.py                   # 0-100 explainable opportunity scoring engine
│   ├── dashboard/
│   │   └── server.py                    # B2B Lead Studio web dashboard & REST API server
│   ├── db/
│   │   ├── database.py                  # SQLite database manager (8 B2B tables + indexes)
│   │   └── models.py                    # Database schema records
│   ├── cli.py                           # CLI entry points (discover, business-cycle, dashboard, etc.)
│   └── config.py                        # Project root and YAML configuration loader
├── tests/                               # 46 TEST MODULES (189 passing tests)
│   ├── test_b2b_approval_gate.py        # Approval enforcement tests
│   ├── test_b2b_db.py                   # SQLite CRUD, indexes, and cascades tests
│   ├── test_b2b_discovery.py            # CSV parsing & deduplication tests
│   ├── test_b2b_integration_acceptance.py# Master 17-step end-to-end lifecycle test
│   ├── test_b2b_intelligence.py        # Analyst, scoring, demo, outreach & response tests
│   └── test_b2b_models.py              # Pydantic entity validation tests
├── hive/                                # Multi-agent coordination system
└── README_MASTER.md                     # Authoritative master documentation
```

### Key Component Dependencies
| Business Function | Primary Source File | Dependencies |
| :--- | :--- | :--- |
| **Lead Discovery** | [`src/b2b/discovery.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/discovery.py) | `src/b2b/models.py`, `src/db/database.py` |
| **Web Research** | [`src/b2b/research_engine.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/research_engine.py) | `src/b2b/models.py`, `src/b2b/research.py` |
| **Opportunity Scoring**| [`src/b2b/scoring.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/scoring.py) | `src/b2b/models.py`, `src/b2b/analyst.py` |
| **Demo Generation** | [`src/b2b/demo_generator.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/demo_generator.py) | `src/b2b/models.py`, `src/b2b/analyst.py` |
| **Outreach Generation**| [`src/b2b/outreach.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/outreach.py) | `src/b2b/models.py`, `src/b2b/scoring.py` |
| **Approval Safety Gate**| [`src/b2b/gatekeeper.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/gatekeeper.py) | `src/b2b/models.py` |
| **Email Delivery** | [`src/b2b/email_provider.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/email_provider.py) | `src/b2b/models.py`, `src/b2b/gatekeeper.py`, `src/db/database.py` |
| **Response & Follow-up**| [`src/b2b/followup.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/followup.py) | `src/b2b/models.py`, `src/b2b/response_classifier.py`, `src/db/database.py` |
| **Web Dashboard** | [`src/dashboard/server.py`](file:///C:/Users/tirth/Desktop/automation/src/dashboard/server.py) | `src/db/database.py`, `src/b2b/pipeline.py`, `src/b2b/email_provider.py` |

---

# 4. DATABASE ARCHITECTURE

### Database Location
- **Default Path**: `output/automation.db` (SQLite 3)

### Schema & Tables

#### 1. `businesses`
- **Columns**: `id` (TEXT PK), `name` (TEXT), `category` (TEXT), `city` (TEXT), `state` (TEXT), `country` (TEXT), `address` (TEXT), `website` (TEXT), `domain` (TEXT), `phone` (TEXT), `email` (TEXT), `source_provider` (TEXT), `source_id` (TEXT), `status` (TEXT), `created_at` (TEXT), `updated_at` (TEXT).
- **Constraints**: `UNIQUE(name, city)`
- **Indexes**: `idx_businesses_domain`, `idx_businesses_category`, `idx_businesses_city`, `idx_businesses_status`.

#### 2. `research_evidence`
- **Columns**: `id` (TEXT PK), `business_id` (TEXT FK -> businesses.id CASCADE), `category` (TEXT), `claim` (TEXT), `claim_type` (TEXT: `verified_fact`, `ai_inference`, `unknown`), `evidence_url` (TEXT), `raw_snippet` (TEXT), `source_type` (TEXT), `confidence` (REAL), `collected_at` (TEXT).
- **Indexes**: `idx_evidence_business`, `idx_evidence_category`, `idx_evidence_type`.

#### 3. `business_research`
- **Columns**: `business_id` (TEXT PK FK -> businesses.id CASCADE), `website_exists` (INTEGER), `website_url` (TEXT), `is_mobile_friendly` (INTEGER), `speed_score` (REAL), `tech_stack_json` (TEXT), `services_json` (TEXT), `pricing_info` (TEXT), `contact_methods_json` (TEXT), `social_links_json` (TEXT), `booking_system_found` (INTEGER), `ordering_system_found` (INTEGER), `observed_weaknesses_json` (TEXT), `observed_strengths_json` (TEXT), `researched_at` (TEXT).

#### 4. `opportunities`
- **Columns**: `id` (TEXT PK), `business_id` (TEXT FK -> businesses.id CASCADE), `opportunity_type` (TEXT), `title` (TEXT), `problem_summary` (TEXT), `proposed_solution` (TEXT), `business_value` (TEXT), `score` (REAL), `score_reasons_json` (TEXT), `risks_json` (TEXT), `confidence` (REAL), `priority` (TEXT), `qualification_status` (TEXT), `evidence_ids_json` (TEXT), `status` (TEXT), `created_at` (TEXT).
- **Indexes**: `idx_opps_business`, `idx_opps_type`, `idx_opps_score`.

#### 5. `demos`
- **Columns**: `id` (TEXT PK), `opportunity_id` (TEXT FK -> opportunities.id CASCADE), `business_id` (TEXT FK -> businesses.id CASCADE), `vertical` (TEXT), `demo_type` (TEXT), `title` (TEXT), `artifact_path` (TEXT), `preview_url` (TEXT), `status` (TEXT), `metadata_json` (TEXT), `created_at` (TEXT).
- **Indexes**: `idx_demos_business`, `idx_demos_opp`.

#### 6. `outreach`
- **Columns**: `id` (TEXT PK), `business_id` (TEXT FK -> businesses.id CASCADE), `opportunity_id` (TEXT FK -> opportunities.id CASCADE), `demo_id` (TEXT FK -> demos.id), `recipient_email` (TEXT), `recipient_name` (TEXT), `subject` (TEXT), `body_text` (TEXT), `body_html` (TEXT), `followup_body` (TEXT), `personalization_reasons_json` (TEXT), `evidence_used_json` (TEXT), `approval_status` (TEXT: `pending_review`, `approved`, `rejected`), `send_status` (TEXT: `draft`, `queued`, `sent`, `failed`), `sent_at` (TEXT), `provider_message_id` (TEXT), `last_error` (TEXT), `created_at` (TEXT).
- **Indexes**: `idx_outreach_business`, `idx_outreach_opp`, `idx_outreach_approval`, `idx_outreach_send`.

#### 7. `outreach_responses`
- **Columns**: `id` (TEXT PK), `outreach_id` (TEXT FK -> outreach.id CASCADE), `business_id` (TEXT FK -> businesses.id CASCADE), `received_at` (TEXT), `classification` (TEXT), `raw_content` (TEXT), `suggested_reply` (TEXT), `reply_status` (TEXT).
- **Indexes**: `idx_responses_outreach`, `idx_responses_business`, `idx_responses_class`.

#### 8. `followups`
- **Columns**: `id` (TEXT PK), `outreach_id` (TEXT FK -> outreach.id CASCADE), `business_id` (TEXT FK -> businesses.id CASCADE), `step_number` (INTEGER), `scheduled_date` (TEXT), `subject` (TEXT), `body_text` (TEXT), `body_html` (TEXT), `status` (TEXT: `pending_review`, `approved`, `sent`, `cancelled`, `suppressed`), `sent_at` (TEXT), `provider_message_id` (TEXT), `last_error` (TEXT), `created_at` (TEXT).
- **Indexes**: `idx_followups_outreach`, `idx_followups_business`, `idx_followups_status`.

### Record Lifecycle Transitions
```
[DiscoveryService]          -> BusinessRecord created (status: DISCOVERED)
[HTTPWebResearchProvider]   -> BusinessResearch & ResearchEvidence created (status: RESEARCHED)
[BusinessAnalyst & Scorer]  -> OpportunityRecord created (status: SCORED)
[DemoGenerator]             -> DemoRecord created & HTML written to disk (status: DEMO_READY)
[OutreachGenerator]         -> OutreachRecord created (status: OUTREACH_READY, approval: PENDING_REVIEW)
[User via Dashboard / CLI]  -> update_outreach_approval (approval: APPROVED)
[OutreachSendingService]    -> send_outreach (send_status: SENT, status: SENT)
[Inbound Ingestion]         -> OutreachResponse created (status: REPLIED)
[FollowUpIntelligence]      -> FollowUpRecord created (status: PENDING_REVIEW)
                                 -> if UNSUBSCRIBED: FollowUpRecord updated (status: SUPPRESSED)
```

---

# 5. API ARCHITECTURE

All endpoints served by `DashboardHandler` in [`src/dashboard/server.py`](file:///C:/Users/tirth/Desktop/automation/src/dashboard/server.py):

| Method | Path | Purpose | Input Payload | Output / DB Effect |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` or `/index.html` | Serves B2B Lead Studio Single Page App | None | Complete interactive HTML/CSS/JS |
| `GET` | `/api/b2b/stats` | Global lead, opportunity, demo, and send stats | None | JSON summary counts |
| `GET` | `/api/b2b/leads` | List all discovered leads | None | JSON array of `BusinessRecord` |
| `GET` | `/api/b2b/leads/<id>` | Full lead dossier bundle (research, opp, demo, outreach) | None | Complete aggregated JSON dossier |
| `POST`| `/api/b2b/pipeline/run`| Execute automated analysis + demo + outreach cycle | `{"provider": "sample", "limit": 5}` | Runs `BusinessIntelligenceService`, updates DB |
| `POST`| `/api/b2b/outreach/<id>/edit` | Edit email subject, body, or recipient | `{"subject": "...", "body_text": "..."}` | Updates `outreach` table |
| `POST`| `/api/b2b/outreach/<id>/approve` | Approve draft for sending | None | Updates `approval_status = 'approved'` |
| `POST`| `/api/b2b/outreach/<id>/reject` | Reject draft | None | Updates `approval_status = 'rejected'` |
| `POST`| `/api/b2b/outreach/<id>/send` | Dispatch outreach (gatekeeper enforced) | `{"force_dry_run": bool, "override_recipient": str}` | Enforces approval; sends via EmailProvider |
| `POST`| `/api/b2b/outreach/<id>/respond` | Ingest and classify prospect reply | `{"message": "..."}` | Creates `OutreachResponse`; auto-suppresses follow-ups if opt-out |
| `GET` | `/api/b2b/responses` | List all received response records | None | JSON array of `OutreachResponse` |
| `GET` | `/api/b2b/followups` | List all staged follow-up records | None | JSON array of `FollowUpRecord` |
| `POST`| `/api/b2b/followups/stage` | Stage due Day 3 / Day 7 follow-ups | None | Generates `FollowUpRecord` rows |
| `POST`| `/api/b2b/followups/<id>/approve` | Approve staged follow-up | None | Updates `status = 'approved'` |
| `POST`| `/api/b2b/followups/<id>/send` | Send approved follow-up | None | Sends follow-up via EmailProvider |
| `POST`| `/api/b2b/feedback/run` | Recompute conservative learning multipliers | None | JSON `FeedbackReport` |
| `GET` | `/demos/<id>/index.html`| Preview generated interactive prototype | None | Serves standalone HTML demo |

---

# 6. CLI ARCHITECTURE

The CLI tool is invoked via `python src/cli.py <command>`:

| Command | Syntax | Purpose | Code Invoked | Safety & Execution Mode |
| :--- | :--- | :--- | :--- | :--- |
| `discover` | `python src/cli.py discover --file <path> --limit 50` | Ingests CSV leads with deduplication | `cmd_discover` -> `DiscoveryService` | Real database writes; idempotent deduplication |
| `leads` | `python src/cli.py leads --city Ahmedabad` | Displays formatted table of leads | `cmd_leads` -> `Database.list_businesses` | Read-only |
| `add-lead` | `python src/cli.py add-lead --name "X" --city "Y"` | Manually adds a lead | `cmd_add_lead` -> `DiscoveryService` | Real database write |
| `business-cycle` | `python src/cli.py business-cycle --demo` | Runs analysis, scoring, demos & outreach | `cmd_business_cycle` -> `BusinessIntelligenceService` | Generates HTML demos in `output/demos/` |
| `b2b-approve` | `python src/cli.py b2b-approve --outreach-id <id>` | Approves draft outreach | `cmd_b2b_approve` -> `db.update_outreach_approval` | Updates approval status |
| `b2b-send` | `python src/cli.py b2b-send --outreach-id <id> [--live]` | Dispatches approved outreach | `cmd_b2b_send` -> `OutreachSendingService` | Gatekeeper enforced; dry-run by default |
| `b2b-respond` | `python src/cli.py b2b-respond --outreach-id <id> --message "..."` | Ingests customer reply & classifies | `cmd_b2b_respond` -> `ingest_response` | Auto-suppresses follow-ups on opt-out |
| `b2b-followup`| `python src/cli.py b2b-followup --stage` | Stages due follow-ups | `cmd_b2b_followup` -> `FollowUpIntelligence` | Stages `PENDING_REVIEW` records |
| `dashboard` | `python src/cli.py dashboard --port 8088` | Launches local web dashboard | `cmd_dashboard` -> `run_dashboard_server` | Local web server |

---

# 7. DASHBOARD ARCHITECTURE

The dashboard is served on `http://127.0.0.1:8088` via [`src/dashboard/server.py`](file:///C:/Users/tirth/Desktop/automation/src/dashboard/server.py).

### Sections
1. **Pipeline Progression Stepper**: Interactive 8-stage visual indicator across the top of the selected lead: `1. Discovered ➔ 2. Researched ➔ 3. Scored ➔ 4. Demo Ready ➔ 5. Outreach Drafted ➔ 6. Approved ➔ 7. Dispatched ➔ 8. Replied`.
2. **Column 1: Business Identity & Verified Research**: Displays business contact details, category, provenance badge (`CSV Ingested`, `Live Scraped`), color-coded verified evidence cards (`Verified Fact`, `AI Inference`, `Unknown`), and identified operational gaps.
3. **Column 2: Scored Opportunity & Interactive Demo**: Displays 0–100 Opportunity Score, confidence badge (`High Confidence` vs `Low Confidence / Insufficient Data`), problem & proposed solution summary, live embedded iframe preview of the generated prototype, and an `Open Full Prototype ↗` button.
4. **Column 3: Personalized Outreach Studio**: Copy editor with recipient email, subject, personalized body text, Day 3 & Day 7 follow-up preview, Send Mode toggle (`Mock Dry-Run` vs `Real SMTP`), Safe Test Recipient Override input, and action controls (`[Save Changes]`, `[✓ Approve Draft]`, `[✗ Reject]`, `[🚀 Dispatch Email]`).
5. **Response & Follow-up Center**: Inbound reply simulator with 4 scenario templates, classification badges, suggested replies, automated opt-out suppression banner (`🛑 Opt-out Suppressed`), and staged follow-up cadence manager.
6. **Sales Intelligence & Funnel**: Conversion metrics and conservative feedback learning status.

---

# 8. AI INTELLIGENCE ARCHITECTURE

Implemented in `src/b2b/` by Ryan (`ryan-mterh0cb`) and integrated by Jim (`jim-mtel249y`):

### 1. Business Analyst ([`src/b2b/analyst.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/analyst.py))
- **Input**: `BusinessRecord` and `BusinessResearch`.
- **Processing**: Evaluates 9 structured diagnostic questions: website existence, mobile responsiveness, online booking presence, online ordering presence, contact channel availability, and observed friction.
- **Output**: Structured `OpportunityRecord` proposals.
- **Guardrail**: Never invents capabilities; unknown channels are cataloged as `ClaimType.UNKNOWN`.

### 2. Opportunity Scorer ([`src/b2b/scoring.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/scoring.py))
- **Input**: Operational gap list, research evidence, vertical commercial profile.
- **Processing**: Computes transparent weighted score: Base Opportunity (0–40) + Gap Severity (0–30) + Digital Readiness (0–20) + Evidence Confidence Multiplier (0.5–1.0).
- **Output**: Final 0–100 score + explainable reason strings.
- **Guardrail**: If evidence is missing or confidence is $< 0.4$, score is heavily penalized and flagged as `LOW CONFIDENCE / INSUFFICIENT DATA`.

### 3. Response Classifier ([`src/b2b/response_classifier.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/response_classifier.py))
- **Input**: Raw customer reply string.
- **Processing**: Multi-class intent matching (`interested`, `wants_meeting`, `wants_pricing`, `question`, `not_interested`, `unsubscribed`, `wrong_contact`).
- **Output**: Classification enum + suggested follow-up response copy.
- **Guardrail**: Strict pattern matching for opt-out keywords (`unsubscribe`, `stop`, `remove me`, `wrong number`, `not interested`).

### 4. Follow-up Intelligence ([`src/b2b/followup.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/followup.py))
- **Input**: Sent outreach records, reply history, suppression list, cadence policy (Day 3 & Day 7).
- **Processing**: Identifies threads due for check-ins without active replies.
- **Output**: `FollowUpRecord` drafts in `PENDING_REVIEW` state.
- **Guardrail**: Absolute suppression for any thread with terminal classifications (`UNSUBSCRIBED`, `WRONG_CONTACT`, `NOT_INTERESTED`).

---

# 9. DEMO GENERATION

Implemented in [`src/b2b/demo_generator.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/demo_generator.py):

### Architecture & Supported Verticals
Every demo is generated as a **standalone, zero-network-dependency HTML5/CSS3/JavaScript application** saved in `output/demos/<demo_id>/index.html`:
1. **Clinic / Dental (`VerticalType.CLINIC`)**: Treatment selector (implants, whitening, root canal), doctor selector (specialist bio & experience), time-slot chips, patient form, and instant WhatsApp booking confirmation modal.
2. **Restaurant / Cafe (`VerticalType.RESTAURANT`)**: Interactive digital menu with dish quantity counters, live bill & GST calculator, direct takeaway order modal, and table reservation form.
3. **Salon & Spa (`VerticalType.SALON`)**: Service packages, master stylist selection, dynamic duration/pricing updates, and instant slot reservation.
4. **Coaching & Academy (`VerticalType.COACHING`)**: Course discovery (IIT-JEE, NEET, Olympiads), syllabus preview, and free demo class seat reservation.
5. **Retail & Grocery (`VerticalType.RETAIL`)**: Product catalog, instant basket calculator, delivery slot picker, and WhatsApp order handoff.
6. **Gym & Fitness (`VerticalType.GYM`)**: Membership plan selector, trainer picker, and 1-day VIP trial pass QR generator.
7. **Real Estate (`VerticalType.REAL_ESTATE`)**: Unit configuration selector (2 BHK / 3 BHK), EMI estimator, and VIP site visit booking.
8. **General SMB (`VerticalType.GENERAL_SMB`)**: Interactive service quotation estimator and callback request modal.

### Data Privacy & Safety Notice
Prototypes contain a clear top notice: *"Simulated client experience — No real patient/customer data transmitted"*. All interactions are client-side JavaScript simulations.

---

# 10. EMAIL ARCHITECTURE

Implemented in [`src/b2b/email_provider.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/email_provider.py):

```
                                  +-----------------------+
                                  |  OutreachRecord Draft |
                                  +-----------------------+
                                              |
                                              v
                              +-------------------------------+
                              | OutreachGatekeeper.can_send() |
                              +-------------------------------+
                                     /                 \
                          [Not Approved]             [Approved]
                                 /                         \
                                v                           v
                     ApprovalGateError Raised      +--------------------------+
                                                   | OutreachSendingService   |
                                                   +--------------------------+
                                                             |
                                         +-------------------+-------------------+
                                         |                                       |
                                         v                                       v
                             [ConsoleEmailProvider]                     [SMTPEmailProvider]
                             (force_dry_run=True)                       (live=True)
                                         |                                       |
                                         v                                       v
                             Writes JSON audit payload                  Sends via SMTP with TLS
                             to output/outreach_staged/                 to recipient or override
```

### Safety Rules
1. **Mandatory Human Approval**: `OutreachGatekeeper` raises `ApprovalGateError` if `approval_status != 'approved'`.
2. **Dry-Run by Default**: Unless explicitly configured with live credentials, all sends use `ConsoleEmailProvider` and save audit logs to `output/outreach_staged/`.
3. **Safe Test Recipient Override**: Supports passing an `override_recipient` (e.g. your personal test email) to verify live delivery without contacting prospects.

---

# 11. RESPONSE & FOLLOW-UP FLOW

### Response Processing
1. Inbound email/message is ingested via `/api/b2b/outreach/<id>/respond` or `python src/cli.py b2b-respond`.
2. `ResponseClassifier` evaluates the message against 7 intent categories.
3. An `OutreachResponse` record is created in SQLite, and the business status updates to `REPLIED`.

### Opt-Out & Safety Behavior
- **`UNSUBSCRIBED`**: Immediately flags the contact as opted out, updates all pending/approved follow-ups for that business to `FollowUpStatus.SUPPRESSED`, and displays `🛑 Auto-Suppressed (Opt-Out Enforced)` in the dashboard.
- **`WRONG_CONTACT`**: Halts automated follow-up cadences.

---

# 12. ANALYTICS & FEEDBACK

Implemented in [`src/b2b/feedback.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/feedback.py):

### Conversion Funnel Metrics
- Discovered Leads ➔ Researched Dossiers ➔ Qualified Opportunities ➔ Tailored Demos Built ➔ Approved Outreach ➔ Dispatched Emails ➔ Inbound Responses ➔ Positive Meetings Won.

### Conservative Learning Rules
- Feedback learning requires **$\ge 5$ real prospect outcomes** before adjusting opportunity scoring multipliers.
- Seeded/demo fixture data is partitioned and does not skew real production conversion statistics.

---

# 13. CURRENT PROJECT STATUS

| Area | Status | Evidence in Code | Remaining Work |
| :--- | :--- | :--- | :--- |
| **Lead Discovery** | COMPLETE | [`src/b2b/discovery.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/discovery.py), CSV ingestion & deduplication passing tests | Connect external search API providers |
| **Web Research** | COMPLETE | [`src/b2b/research_engine.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/research_engine.py), live HTTP auditing with 10s timeout | Add headless browser rendering for heavy SPA sites |
| **Database** | COMPLETE | [`src/db/database.py`](file:///C:/Users/tirth/Desktop/automation/src/db/database.py), 8 B2B tables with foreign keys and indexes | Optional Postgres migration script |
| **Business Analysis**| COMPLETE | [`src/b2b/analyst.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/analyst.py), 9 gap evaluations | Expand niche vertical questionnaires |
| **Opportunity Scoring**| COMPLETE | [`src/b2b/scoring.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/scoring.py), 0-100 explainable scoring | Refine sector-specific revenue models |
| **Demo Generation**| COMPLETE | [`src/b2b/demo_generator.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/demo_generator.py), 8 rich vertical prototypes | Add live booking webhook integrations |
| **Outreach Synthesis**| COMPLETE | [`src/b2b/outreach.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/outreach.py), evidence-cited drafts | Add multi-lingual email templates (Hindi/Gujarati) |
| **Approval Safety Gate**| COMPLETE | [`src/b2b/gatekeeper.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/gatekeeper.py), strict validation | None (fully enforced) |
| **Email Delivery** | COMPLETE | [`src/b2b/email_provider.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/email_provider.py), Console & SMTP providers | Add SendGrid/Postmark API adapters |
| **Response Classifier**| COMPLETE | [`src/b2b/response_classifier.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/response_classifier.py), 7-class classifier | Add fine-tuned LLM classifier |
| **Follow-up Cadence**| COMPLETE | [`src/b2b/followup.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/followup.py), Day 3/7 staging + auto-suppression | None (fully enforced) |
| **Web Dashboard** | COMPLETE | [`src/dashboard/server.py`](file:///C:/Users/tirth/Desktop/automation/src/dashboard/server.py), full Single Page Application | Add user authentication for multi-user sales teams |
| **Analytics & Learning**| COMPLETE | [`src/b2b/feedback.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/feedback.py), conservative multiplier engine | Expand cohort analytics |

---

# 14. CURRENT TEST STATUS

- **Targeted Acceptance Test**: [`tests/test_b2b_integration_acceptance.py`](file:///C:/Users/tirth/Desktop/automation/tests/test_b2b_integration_acceptance.py) (17-step end-to-end flow: **PASSED**).
- **Full Regression Suite**: `python -m pytest -q`
  - **Passed**: 189
  - **Skipped**: 1 (Legacy external video composition test)
  - **Failed**: 0
  - **Total Modules**: 46
  - **Execution Time**: ~71 seconds

---

# 15. HOW TO RUN THE PROJECT

### Environment & Dependencies
```powershell
# Prerequisites: Python 3.10+ on Windows / Linux / macOS
cd C:\Users\tirth\Desktop\automation
python -m pip install -r requirements.txt
```

### Starting the Dashboard Server
```powershell
python src/cli.py dashboard --port 8088
```
Open **[http://127.0.0.1:8088](http://127.0.0.1:8088)** in your browser.

### Running Discovery & Ingestion
```powershell
python src/cli.py discover --file data/indian_businesses_sample.csv --limit 20
```

### Running Intelligence Cycle (Analysis, Scoring, Demos, Outreach)
```powershell
python src/cli.py business-cycle --demo
```

### Running Test Suite
```powershell
python -m pytest tests/test_b2b_integration_acceptance.py
python -m pytest -q
```

---

# 16. END-TO-END WORKFLOW EXAMPLE

Here is the exact progression of a lead through the codebase:

1. **Discovery** ([`src/b2b/discovery.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/discovery.py)): `Apex Smile Dental Care` is ingested from CSV, checked against existing domain and normalized name+city pairs, and saved with `status = 'discovered'`.
2. **Research** ([`src/b2b/research_engine.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/research_engine.py)): `HTTPWebResearchProvider` inspects the website, identifies treatments offered (implants, whitening), notes absence of online booking widgets, catalogs phone-only contact flow, and saves structured claims to `research_evidence`.
3. **AI Gap Analysis** ([`src/b2b/analyst.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/analyst.py)): `BusinessAnalyst` evaluates the 9 questions and diagnoses a missing online appointment flow.
4. **Opportunity Scoring** ([`src/b2b/scoring.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/scoring.py)): `OpportunityScorer` calculates a score of 81.0/100, assigns `HIGH` priority, and saves an `OpportunityRecord`.
5. **Demo Generation** ([`src/b2b/demo_generator.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/demo_generator.py)): `DemoGenerator` renders a tailored clinic appointment prototype in `output/demos/demo_xxx/index.html` with doctor selection and instant WhatsApp reminders.
6. **Outreach Synthesis** ([`src/b2b/outreach.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/outreach.py)): `OutreachGenerator` crafts personalized email copy citing their clinic treatments and demo link, saving an `OutreachRecord` with `approval_status = 'pending_review'`.
7. **Human Approval** ([`src/dashboard/server.py`](file:///C:/Users/tirth/Desktop/automation/src/dashboard/server.py)): SDR reviews the lead dossier in the dashboard and clicks `[✓ Approve Draft]`.
8. **Sending** ([`src/b2b/email_provider.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/email_provider.py)): `OutreachSendingService` checks the approval gate, executes delivery (dry-run audit or live SMTP), and updates state to `SENT`.
9. **Inbound Reply** ([`src/b2b/response_classifier.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/response_classifier.py)): Inbound response is classified as `INTERESTED`, generating a suggested meeting confirmation reply.
10. **Opt-Out Check** ([`src/b2b/pipeline.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/pipeline.py)): If the response had been `UNSUBSCRIBED`, all pending follow-ups would be immediately marked `SUPPRESSED`.
11. **Conversion Analytics** ([`src/b2b/feedback.py`](file:///C:/Users/tirth/Desktop/automation/src/b2b/feedback.py)): The outcome is recorded in conversion history for conservative feedback optimization.

---

# 17. WHAT IS REAL VS MOCKED

### Real / Implemented
- SQLite schema, foreign keys, indexes, cascades, and data persistence.
- CSV parsing, header normalization, delimiter sniffing, and 3-tier lead deduplication.
- Live HTTP web scraping with rate-limiting, viewport inspections, and structured evidence assembly.
- Opportunity gap analysis, transparent 0–100 scoring, and explainable score reasoning.
- 8 vertical-specific interactive HTML/JS prototype templates written to disk in `output/demos/`.
- Human approval enforcement gatekeeper.
- Multi-class NLP response classifier and auto-suggested reply generation.
- Automated opt-out suppression for `UNSUBSCRIBED` and `WRONG_CONTACT`.
- B2B Lead Studio Single Page Application dashboard and REST API.

### Mock / Dry-Run
- **`ConsoleEmailProvider`**: Default email provider. Validates approval gates and saves audit JSON payloads to `output/outreach_staged/` without sending network packets.
- **Inbound Reply Simulator**: Web UI tool to simulate customer responses across 4 standard scenario templates.

### Seeded / Demo Data
- **`data/indian_businesses_sample.csv`**: Seed dataset of 20 Indian SMBs for offline exploration.
- **`src/b2b/fixtures.py`**: Static research provider (`static_sample`) for fast offline development and testing.

---

# 18. KNOWN PROBLEMS / LIMITATIONS

1. **External SMTP Configuration Required for Live Sending**: Live prospect emailing requires setting `smtp_host`, `smtp_username`, and `smtp_password` in `config/config.yaml`.
2. **Client-Side Prototypes**: Prototype HTML files run client-side JavaScript. They do not persist simulated bookings into a backend database unless connected to a live webhook.
3. **Scraper Limitations on JS-Heavy Single Page Apps**: The `HTTPWebResearchProvider` parses raw HTML via `urllib.request`. Sites that render 100% via client-side React/Vue without SSR may return limited raw text.
4. **Single-User Dashboard**: The dashboard currently lacks multi-tenant user authentication or role-based access control (RBAC).

---

# 19. PRIORITIZED ROADMAP

### P0 — Must Fix Before Production Outbound
- [x] Strict human approval gate before email sending (*Complete*).
- [x] Automated opt-out suppression for unsubscribes (*Complete*).
- [x] Client-specific vertical prototype generation (*Complete*).
- [ ] Add SendGrid / Postmark API adapters alongside SMTP for high-deliverability enterprise emailing.

### P1 — Important Product Improvements
- [ ] Integrate headless Chromium (e.g. Playwright) for scraping JavaScript-heavy single-page applications.
- [ ] Add CRM webhook exports (HubSpot, Salesforce, Pipedrive) for leads reaching `REPLIED` status.
- [ ] Add multi-lingual outreach copy synthesis (Hindi, Marathi, Gujarati, Tamil).

### P2 — Future Scale & Platform Improvements
- [ ] Multi-tenant authentication and role-based permissions for sales teams.
- [ ] Live customer booking webhook receiver to connect prototype forms to real prospect calendars.

---

# 20. RULES FOR FUTURE AI/CODING AGENTS (ANTIGRAVITY)

1. **Read README_MASTER.md before modifying code.**
2. **Inspect the actual codebase before assuming behavior.** Never guess APIs or database column names.
3. **Do not rewrite working systems unnecessarily.** Preserve working discovery, research, scoring, demo generation, and approval infrastructure.
4. **Preserve existing tests and run pytest after changes.** Ensure all 189 tests remain green.
5. **Never fabricate business facts or invent live contact data.** If research data is missing, tag it as `ClaimType.UNKNOWN`.
6. **Never manufacture opportunity scores from insufficient evidence.** Show `LOW CONFIDENCE / INSUFFICIENT DATA` instead.
7. **Never send real outreach without explicit human approval.** The `OutreachGatekeeper` must remain mandatory.
8. **Never treat dry-run simulation as real email delivery.**
9. **Respect unsubscribe and opt-out signals unconditionally.**
10. **Preserve SQLite database compatibility and existing migrations.**
11. **Do not modify or delete the hive coordination infrastructure.**
12. **Keep B2B Client Outreach as the sole project direction.** Do not re-introduce YouTube or consumer video generation architectures.
13. **Update README_MASTER.md** whenever the architecture, database schema, or project status changes materially.
