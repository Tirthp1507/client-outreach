# AI Content Automation System

Topic-to-short-video pipeline. Give it a topic, get an MP4 for YouTube Shorts /
Instagram Reels back.

```
Topic → Script → Voice (Edge-TTS) → Video compositor (FFmpeg) → 1080x1920 MP4
```

Built incrementally under the Phase 1 MVP plan (see DEVELOPMENT_PLAN.md).
The `hive/` directory is the multi-agent orchestrator — do not touch it.

## Requirements

- Python 3.10+
- FFmpeg **on PATH** (or set `FFMPEG_BIN`) — required only for the final
  video rendering stage. Install with `winget install Gyan.FFmpeg` or from
  https://ffmpeg.org. The script and voiceover stages run without it.
- Network access for Edge-TTS (Microsoft's free voice service).

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optionally copy `config/.env.example` to `config/.env` and fill in secrets.
Never commit the real `.env`.

## Usage

### 1. Generate Video from Topic (Phase 1)
```powershell
python src/cli.py generate --topic "Top 3 productivity hacks"
python src/cli.py generate --topic "..." --provider openai
python src/cli.py generate --topic "..." --no-video     # script + voice only
python src/cli.py doctor                                 # environment check
```

### 2. Collect and Process Content (Phase 2)
```powershell
# Ingest raw items from RSS feeds (and Reddit)
python src/cli.py collect
python src/cli.py collect --sources rss --limit 15

# Clean, deduplicate, rank, and summarize candidates
python src/cli.py process
python src/cli.py process --limit 5
```

### 3. Automated End-to-End Generation (Phases 3 & 4)
```powershell
# Ingest -> Process -> Select top candidate -> Generate complete Short MP4
python src/cli.py auto --limit 1

# Generate top candidate with min score threshold
python src/cli.py auto --limit 1 --min-score 40.0

# Generate using existing processed items (skips fetching)
python src/cli.py auto --skip-collect --limit 1
```

### 4. Approval Studio & Scheduled Batch Automation (Phase 5)
```powershell
# Run scheduled batch cycle (saves jobs to SQLite with PENDING_REVIEW status)
python src/cli.py schedule --limit 1

# Start the local human approval studio web server
python src/cli.py dashboard --port 8080
```
Open **`http://127.0.0.1:8080`** to review generated videos, inspect AI strategy classifications, edit titles/captions, and click **Approve** / **Reject** / **Publish (Dry-Run)** / **Publish (Live)**.

### 5. Production Publishing & Distribution (Phase 7)
```powershell
# Publish approved job to YouTube Shorts in dry-run mode (safe validation)
python src/cli.py publish --job-id <job_id> --platform youtube --dry-run

# Publish approved job to Instagram Reels in dry-run mode
python src/cli.py publish --job-id <job_id> --platform instagram --dry-run

# Publish approved job to all platforms in dry-run mode
python src/cli.py publish --job-id <job_id> --platform all --dry-run

# Check detailed publishing status, URL, and attempt history for a job
python src/cli.py publish-status --job-id <job_id>

# Run environment & publishing diagnostics
python src/cli.py doctor
```

### 6. Performance Analytics & Feedback Loop (Phase 9)
```powershell
# Collect and record latest performance snapshots for all eligible jobs
python src/cli.py sync-metrics --dry-run

# Inspect historical views, retention, and engagement snapshots for a specific job
python src/cli.py analytics --job-id <job_id>

# View global performance summary and format/hook breakdown report
python src/cli.py analytics-summary
python src/cli.py analytics-summary --platform youtube

# Run AI intelligence engine to identify performance correlations
python src/cli.py intelligence
```

### 7. Production Daemon & Operational Safeguards (Phase 10)
```powershell
# Run long-running continuous automation daemon (every 60 mins)
python src/cli.py daemon --interval-minutes 60 --limit 1

# Execute a single automated maintenance cycle (suitable for task schedulers)
python src/cli.py daemon --once --dry-run

# Inspect operational safeguards, daily quotas, and system health
python src/cli.py safeguards

# Inspect automated execution cycle audit history
python src/cli.py audit --limit 20

# Clean up stale intermediate drafts and audio older than 7 days
python src/cli.py prune --days 7 --dry-run
```



Output lands under `output/`:

```
output/
├── automation.db                  SQLite database for persistent job lifecycle & approval
├── history.json                   job tracking & duplicate prevention store
├── collected/latest.json          raw collected feed items
├── processed/latest.json          ranked and summarized candidates
├── scripts/  <slug>.json          structured script with visual cues, strategy, & provenance
├── audio/    <slug>.mp3           voiceover
├── drafts/   <slug>.ass|.srt      burned-in animated karaoke subtitle sources
├── drafts/   <slug>.timings.json  per-word TTS timestamps
├── final/    <slug>.mp4           publish-ready 1080x1920 video
├── final/    <slug>_thumb.jpg     extracted 1080x1920 thumbnail frame
├── final/    <slug>.publish.json  YouTube & Instagram captions, titles, and hashtags
├── final/    <slug>.meta.json     video metadata, provenance, strategy, & QA quality score
└── publish_staged/                verified JSON upload payloads for YouTube and Instagram
```


## Script providers

- `template` (default) — deterministic, offline, no API key. Great for smoke
  tests; content is generic placeholders.
- `openai` — any OpenAI-compatible endpoint (`OPENAI_API_KEY`,
  `OPENAI_BASE_URL=https://.../v1`, `OPENAI_MODEL`). Works with OpenAI,
  Azure, Ollama (`http://localhost:11434/v1`), LM Studio, etc.

The provider is an interface (`src/generators/base.py`); add a new backend by
implementing one class and registering it in
`src/generators/script_generator.py::PROVIDERS`.

## Voice engine

`src/voice/base.py` defines the TTS interface. The Edge-TTS implementation
(`src/voice/edge_tts_engine.py`) also returns word-level timestamps used to
build timed captions via `src/voice/subtitle_aligner.py`. ElevenLabs and
friends can be added as sibling engines without touching the pipeline.

## Tests

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest tests/ -v
```

Tests that need Edge-TTS, network, or FFmpeg self-skip when unavailable.

## Layout

```
assets/      reusable background media, fonts, music (drop MP4/JPG here)
config/config.yaml      defaults (env vars override)
config/.env.example     secrets template
src/         generators | voice | video | pipeline | cli
tests/       pytest suite
output/      generated artifacts (gitignored)
```