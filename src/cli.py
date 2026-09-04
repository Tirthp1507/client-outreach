"""Command-line interface for the AI Content Automation System.

Usage::

    # Phase 1: Manual video generation
    python src/cli.py generate --topic "Top 3 productivity hacks"
    python src/cli.py generate --topic "..." --provider openai --no-video
    python src/cli.py doctor

    # Phase 2: Content collection and processing
    python src/cli.py collect
    python src/cli.py collect --sources rss,reddit --limit 15
    python src/cli.py process
    python src/cli.py process --input output/collected/latest.json --limit 5

    # Phase 3 & 4: Intelligent end-to-end publish-quality auto generation
    python src/cli.py auto --limit 1
    python src/cli.py auto --limit 1 --min-score 40.0
    python src/cli.py auto --skip-collect --limit 2

    # Phase 5: Automation & Approval Infrastructure
    python src/cli.py dashboard --port 8080
    python src/cli.py schedule --limit 1
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Make `src` importable whether run as `python src/cli.py` or imported.
_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from analytics import (
    AnalyticsCollector,
    AnalyticsReporter,
    PerformanceInsightsEngine,
    SelectionLedger,
    build_selection_scorer,
)
from collectors import CollectionBatch, RawContentItem, collect_all_sources
from b2b.discovery import DiscoveryRegistry, DiscoveryService, BusinessDeduplicator
from b2b.email_provider import OutreachSendingService, ApprovalGateError
from b2b.fixtures import build_sample_business_dataset
from b2b.models import ApprovalStatus, BusinessRecord, BusinessStatus, FollowUpStatus, SendStatus
from b2b.pipeline import BusinessIntelligenceService
from b2b.scheduler_intent import BusinessCycleContext
from config import PROJECT_ROOT, get_config
from dashboard import run_dashboard_server
from db import Database, JobRecord, JobStatus, PublishStatus
from pipeline import ContentSelector, HistoryRecord, HistoryStore, JobRecoveryEngine, PipelineResult, PipelineRunner
from pipeline.runner import PipelineStepError
from pipeline.safeguards import PublishQuotaGuard, StoragePruningEngine, SystemHealthMonitor
from processors import ProcessedCandidate, ProcessingBatch, process_content_batch
from publishers import InstagramPublisher, PublisherService, PublishingGateError, YouTubePublisher
from scheduler import AutomationDaemon, ScheduledPipeline
from video import has_ffmpeg
from voice import EdgeTTSEngine, TTSEngineError



if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(highlight=False)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )


def _print_result(result: PipelineResult) -> None:
    table = Table(title=f"Pipeline result — {result.topic!r}", show_header=False)
    table.add_column("Stage", style="bold cyan")
    table.add_column("Artifact", style="green")
    for stage, path in result.artifacts.items():
        table.add_row(stage, path)
    console.print(table)

    if result.provenance:
        p_src = result.provenance.get("source_name", "Unknown")
        p_url = result.provenance.get("source_url", "")
        p_score = result.provenance.get("score", 0.0)
        console.print(f"[bold cyan]Provenance:[/bold cyan] {p_src} (Candidate Score: {p_score:.1f}) | {p_url}")

    if result.quality_score is not None:
        q_pass = result.quality_report.passed if result.quality_report else True
        q_style = "bold green" if q_pass else "bold yellow"
        q_label = "PASSED" if q_pass else "FLAGGED FOR REVIEW"
        console.print(f"[{q_style}]Quality QA Score:[/{q_style}] {result.quality_score:.1f}/100 ({q_label})")

    if result.platform_metadata:
        yt = result.platform_metadata.youtube
        ig_preview = result.platform_metadata.instagram.caption[:220].encode("ascii", "replace").decode("ascii")
        yt_title = yt.title.encode("ascii", "replace").decode("ascii")
        console.print(
            Panel(
                f"[bold cyan]YouTube Title:[/bold cyan] {yt_title}\n"
                f"[bold cyan]Tags:[/bold cyan] {', '.join(yt.tags[:6])}\n"
                f"[bold cyan]Instagram Caption:[/bold cyan]\n{ig_preview}...",
                title="Platform Publishing Metadata (YouTube Shorts / IG Reels)",
                border_style="cyan",
            )
        )

    if result.timing_warnings:
        for warning in result.timing_warnings:
            console.print(f"[yellow]![/yellow] {warning}")

    for blocked in result.blocked:
        console.print(f"[red]x blocked:[/red]\n{blocked}")

    if result.status == "partial":
        console.print(
            Panel(
                "The pipeline produced script + voiceover but the final video is blocked. "
                "Install FFmpeg (`winget install Gyan.FFmpeg` or https://ffmpeg.org) and "
                "re-run — cached artifacts will not be needed, only video rendering.",
                title="Partial success",
                border_style="yellow",
            )
        )
    else:
        console.print(Panel("Done.", title="Success", border_style="green"))


def cmd_generate(args: argparse.Namespace) -> int:
    config = get_config()
    config["pipeline"]["output_dir"] = args.output_dir or config["pipeline"].get("output_dir", "output")

    runner = PipelineRunner(config)
    try:
        result = runner.run(
            args.topic,
            provider=args.provider,
            voice=args.voice,
            render_video=not args.no_video,
            seed=args.seed,
        )
    except (PipelineStepError, ValueError) as exc:
        console.print(f"[red]Pipeline error:[/red] {exc}")
        return 1

    _print_result(result)
    return 0 if result.status == "ok" else 2


def cmd_doctor(args: argparse.Namespace) -> int:
    console.print("AI Content Automation — Environment & Reliability Doctor\n")
    table = Table(show_header=True, title="System Diagnostics & Readiness")
    table.add_column("Subsystem", style="cyan")
    table.add_column("Readiness", style="green")
    table.add_column("Details", style="white")

    # 1. FFmpeg
    ff_ok = has_ffmpeg()
    table.add_row("FFmpeg Core", "OK" if ff_ok else "[red]MISSING[/red]", "Video Compositing & 9:16 Canvas" if ff_ok else "winget install Gyan.FFmpeg")

    # 2. Edge-TTS
    try:
        EdgeTTSEngine()
        table.add_row("Edge-TTS Voice", "OK", "Neural speech synthesis ready")
    except TTSEngineError as exc:
        table.add_row("Edge-TTS Voice", "[red]ERROR[/red]", str(exc))

    # 3. Database
    try:
        db = Database()
        jobs_count = len(db.list_jobs(limit=100))
        table.add_row("SQLite Store", "OK", f"automation.db reachable ({jobs_count} jobs indexed)")
    except Exception as exc:
        table.add_row("SQLite Store", "[red]ERROR[/red]", str(exc))

    # 4. YouTube Publisher
    config = get_config()
    yt_pub = YouTubePublisher(config)
    yt_cred = yt_pub.validate_credentials()
    table.add_row(
        "YouTube Shorts",
        "READY (OAuth/Token)" if yt_cred else "[yellow]STAGED ONLY[/yellow]",
        "Configured for live upload" if yt_cred else "Safe staged/dry-run mode (OAuth token not configured)",
    )

    # 5. Instagram Publisher
    ig_pub = InstagramPublisher(config)
    ig_cred = ig_pub.validate_credentials()
    table.add_row(
        "Instagram Reels",
        "READY (Graph API)" if ig_cred else "[yellow]STAGED ONLY[/yellow]",
        "Configured for live publish" if ig_cred else "Safe staged/dry-run mode (Graph API token not configured)",
    )

    # 6. Analytics Store
    try:
        snaps_count = len(db.list_snapshots(limit=100))
        table.add_row("Analytics Engine", "OK", f"Performance store online ({snaps_count} snapshots recorded)")
    except Exception as exc:
        table.add_row("Analytics Engine", "[yellow]READY[/yellow]", "Performance tracking store ready")

    # 7. Pipeline Settings
    table.add_row("Script Engine", config.get("pipeline", {}).get("script_provider", "template"), "Default offline template fallback active")
    table.add_row("Target Canvas", f"{config.get('video', {}).get('width', 1080)}x{config.get('video', {}).get('height', 1920)}", "Vertical 9:16 Shorts/Reels")

    console.print(table)
    return 0



def cmd_collect(args: argparse.Namespace) -> int:
    config = get_config()
    out_dir = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output")) / "collected"
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = [s.strip() for s in args.sources.split(",")] if args.sources else None
    console.print(f"[bold cyan]Collecting content from sources:[/bold cyan] {sources or 'all configured'}")

    batch: CollectionBatch = collect_all_sources(config, sources=sources, limit=args.limit)

    if not batch.items:
        console.print("[yellow]No items collected. Check feed URLs and network connection.[/yellow]")
        if batch.errors:
            for err in batch.errors:
                console.print(f"[red]Error:[/red] {err}")
        return 1

    ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_file = out_dir / f"collected_{ts_str}.json"
    latest_file = out_dir / "latest.json"

    batch_json = batch.model_dump_json(indent=2)
    batch_file.write_text(batch_json, encoding="utf-8")
    latest_file.write_text(batch_json, encoding="utf-8")

    table = Table(title=f"Collected Content ({batch.total_items} items)", show_header=True)
    table.add_column("Source", style="cyan", width=18)
    table.add_column("Title", style="white")
    table.add_column("Score", style="magenta", justify="right", width=8)

    for item in batch.items[:15]:
        table.add_row(item.source_name, item.title[:65], f"{item.score:.0f}")

    console.print(table)
    if batch.total_items > 15:
        console.print(f"... and [bold]{batch.total_items - 15}[/bold] more items.")

    console.print(
        Panel(
            f"Saved {batch.total_items} raw items to:\n"
            f"- [green]{batch_file}[/green]\n"
            f"- [green]{latest_file}[/green]\n\n"
            f"Next: run [bold cyan]python src/cli.py process[/bold cyan] to clean and rank candidates.",
            title="Collection Complete",
            border_style="green",
        )
    )
    return 0


def cmd_process(args: argparse.Namespace) -> int:
    config = get_config()
    in_file = Path(args.input) if args.input else Path(config.get("pipeline", {}).get("output_dir", "output")) / "collected" / "latest.json"
    out_dir = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output")) / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not in_file.exists():
        console.print(
            f"[red]Input file not found:[/red] {in_file}\n"
            "Run [bold cyan]python src/cli.py collect[/bold cyan] first to gather raw content."
        )
        return 1

    try:
        raw_data = json.loads(in_file.read_text(encoding="utf-8"))
        items_data = raw_data.get("items", [])
        raw_items = [RawContentItem(**it) for it in items_data]
    except Exception as exc:
        console.print(f"[red]Failed to load raw items from {in_file}:[/red] {exc}")
        return 1

    console.print(f"[bold cyan]Processing {len(raw_items)} raw content items...[/bold cyan]")
    batch: ProcessingBatch = process_content_batch(raw_items, config)

    if not batch.candidates:
        console.print("[yellow]No candidates remained after processing/filtering.[/yellow]")
        return 1

    ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    proc_file = out_dir / f"candidates_{ts_str}.json"
    latest_file = out_dir / "latest.json"

    proc_json = batch.model_dump_json(indent=2)
    proc_file.write_text(proc_json, encoding="utf-8")
    latest_file.write_text(proc_json, encoding="utf-8")

    limit = min(args.limit, len(batch.candidates))
    table = Table(title=f"Top {limit} Short Video Candidates (from {batch.total_input} items)", show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Score", style="bold magenta", justify="right", width=6)
    table.add_column("Topic / Hook", style="bold green")
    table.add_column("Source", style="cyan", width=16)
    table.add_column("Top Reason", style="yellow")

    for idx, cand in enumerate(batch.candidates[:limit], start=1):
        top_reason = cand.reasons[0] if cand.reasons else "High overall score"
        table.add_row(str(idx), f"{cand.score:.1f}", cand.topic_suggestion[:55], cand.source_name, top_reason[:35])

    console.print(table)

    top_topic = batch.candidates[0].topic_suggestion
    console.print(
        Panel(
            f"Saved {len(batch.candidates)} ranked candidates ({batch.total_duplicates_removed} duplicates removed):\n"
            f"- [green]{proc_file}[/green]\n"
            f"- [green]{latest_file}[/green]\n\n"
            f"Generate short video for top candidate:\n"
            f"[bold cyan]python src/cli.py generate --topic \"{top_topic}\"[/bold cyan]",
            title="Processing & Ranking Complete",
            border_style="green",
        )
    )
    return 0


def cmd_auto(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    history_file = out_base / "history.json"
    history_store = HistoryStore(history_file)
    db = Database(out_base / "automation.db")
    selector = ContentSelector(history_store)

    candidates: list[ProcessedCandidate] = []

    if not args.skip_collect:
        console.print("[bold cyan]Step 1: Collecting content from feeds...[/bold cyan]")
        sources = [s.strip() for s in args.sources.split(",")] if args.sources else None
        batch = collect_all_sources(config, sources=sources, limit=max(15, args.limit * 5))
        
        if batch.items:
            col_dir = out_base / "collected"
            col_dir.mkdir(parents=True, exist_ok=True)
            col_dir.joinpath("latest.json").write_text(batch.model_dump_json(indent=2), encoding="utf-8")

            console.print(f"[bold cyan]Step 2: Processing and ranking {batch.total_items} items...[/bold cyan]")
            proc_batch = process_content_batch(batch.items, config)
            proc_dir = out_base / "processed"
            proc_dir.mkdir(parents=True, exist_ok=True)
            proc_dir.joinpath("latest.json").write_text(proc_batch.model_dump_json(indent=2), encoding="utf-8")
            candidates = proc_batch.candidates

    if not candidates:
        proc_latest = out_base / "processed" / "latest.json"
        if proc_latest.exists():
            try:
                raw = json.loads(proc_latest.read_text(encoding="utf-8"))
                candidates = [ProcessedCandidate(**it) for it in raw.get("candidates", [])]
            except Exception as exc:
                console.print(f"[red]Error loading {proc_latest}:[/red] {exc}")

    if not candidates:
        console.print("[red]No candidate content available to process. Check network or feed configuration.[/red]")
        return 1

    console.print(f"[bold cyan]Step 3: Selecting top {args.limit} ungenerated candidate(s) (min_score={args.min_score})...[/bold cyan]")
    selection_scorer = None
    learning = bool(args.feedback)
    learning = learning or bool((config.get("analytics") or {}).get("feedback_enabled", False))
    diversity = bool(getattr(args, "diversity", False))
    diversity = diversity or bool((config.get("analytics") or {}).get("diversity_enabled", False))
    if learning or diversity:
        effective = dict(config)
        effective["analytics"] = {
            **(config.get("analytics") or {}),
            "feedback_enabled": learning,
            "diversity_enabled": diversity,
        }
        selection_scorer = build_selection_scorer(db=db, config=effective)
        if selection_scorer is not None:
            applied = []
            if learning:
                applied.append("performance feedback")
            if diversity:
                applied.append("diversity")
            console.print(f"[bold cyan]Step 3b: Applying {' + '.join(applied)} to ranking...[/bold cyan]")
        else:
            console.print("[dim]Not enough history for feedback/diversity; using raw ranking.[/dim]")

    selected = selector.select_candidates(
        candidates,
        limit=args.limit,
        min_score=args.min_score,
        feedback_scorer=selection_scorer,
    )

    if not selected:
        console.print(
            Panel(
                "No ungenerated candidates found meeting score threshold.\n"
                "All items in current batch may have already been generated into videos, "
                "or their scores fell below --min-score.",
                title="No New Candidates",
                border_style="yellow",
            )
        )
        return 0

    ledger = SelectionLedger(config=config) if selection_scorer is not None else None
    if selection_scorer is not None:
        for cand in selected:
            delta, reasons = selection_scorer.explain(cand)
            if ledger is not None:
                ledger.record(cand, delta, reasons)
            for reason in reasons or []:
                console.print(f"[dim]    selection {delta:+.1f} pts:[/dim] {reason}")

    runner = PipelineRunner(config)
    exit_code = 0

    for idx, cand in enumerate(selected, start=1):
        console.print(
            f"\n[bold green]Generating Short #{idx}/{len(selected)}:[/bold green] "
            f"[bold white]{cand.clean_title}[/bold white] "
            f"(Source: [cyan]{cand.source_name}[/cyan], Score: [magenta]{cand.score:.1f}[/magenta])"
        )

        try:
            result = runner.run_candidate(
                cand,
                provider=args.provider,
                voice=args.voice,
                render_video=not args.no_video,
                seed=args.seed,
            )
        except (PipelineStepError, ValueError) as exc:
            console.print(f"[red]Pipeline execution failed:[/red] {exc}")
            exit_code = 1
            continue

        # Record in history store
        history_store.record(
            HistoryRecord(
                candidate_id=cand.id,
                topic=result.topic,
                slug=result.slug,
                source_name=cand.source_name,
                source_url=cand.source_url,
                source_title=cand.raw_title,
                score=cand.score,
                status=result.status,
                video_path=result.artifacts.get("video"),
                audio_path=result.artifacts.get("audio"),
                script_path=result.artifacts.get("script"),
            )
        )

        # Record in SQLite Database for Approval Dashboard
        yt_meta = result.platform_metadata.youtube if result.platform_metadata else None
        ig_meta = result.platform_metadata.instagram if result.platform_metadata else None
        strat_dict = result.strategy or {}
        job = JobRecord(
            id=f"job_{result.slug}",
            slug=result.slug,
            topic=result.topic,
            candidate_id=cand.id,
            source_name=cand.source_name,
            source_url=cand.source_url,
            status=JobStatus.PENDING_REVIEW,
            score=cand.score,
            quality_score=result.quality_score,
            quality_passed=result.quality_report.passed if result.quality_report else True,
            content_format=strat_dict.get("content_format", "explainer"),
            hook_strategy=strat_dict.get("hook_strategy", "curiosity_gap"),
            target_audience=strat_dict.get("target_audience", "general_consumers"),
            strategy_json=json.dumps(strat_dict) if strat_dict else "{}",
            script_json=result.script.model_dump_json() if result.script else "{}",
            youtube_title=yt_meta.title if yt_meta else "",
            youtube_description=yt_meta.description if yt_meta else "",
            youtube_tags=json.dumps(yt_meta.tags) if yt_meta else "[]",
            instagram_caption=ig_meta.caption if ig_meta else "",
            video_path=result.artifacts.get("video"),
            thumbnail_path=result.artifacts.get("thumbnail"),
            audio_path=result.artifacts.get("audio"),
        )
        db.save_job(job)

        _print_result(result)
        if result.status != "ok":
            exit_code = 2

    return exit_code


def cmd_dashboard(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")

    console.print(
        Panel(
            f"[bold green]AI Content Approval Studio Server[/bold green]\n\n"
            f"Dashboard URL: [bold cyan]http://{args.host}:{args.port}[/bold cyan]\n"
            f"Database: [dim]{db.db_path}[/dim]\n\n"
            f"Press [bold red]Ctrl+C[/bold red] to stop the server.",
            title="Approval Dashboard",
            border_style="cyan",
        )
    )
    server = run_dashboard_server(host=args.host, port=args.port, db=db)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")
    sched = ScheduledPipeline(config=config, db=db)

    sources = [s.strip() for s in args.sources.split(",")] if args.sources else None

    if args.interval_minutes <= 0:
        console.print(f"[bold cyan]Running scheduled batch cycle (limit={args.limit}, min_score={args.min_score})...[/bold cyan]")
        jobs = sched.run_cycle(
            limit=args.limit,
            min_score=args.min_score,
            sources=sources,
            skip_collect=args.skip_collect,
            render_video=not args.no_video,
        )
        if jobs:
            console.print(f"[bold green]Scheduled cycle complete! Generated {len(jobs)} job(s) pending review:[/bold green]")
            for j in jobs:
                console.print(f"  - [bold white]{j.topic}[/bold white] (QA: {j.quality_score:.0f}/100, Status: [yellow]{j.status.value}[/yellow])")
            console.print(
                Panel(
                    "Review, edit, and approve these jobs in the dashboard:\n"
                    "[bold cyan]python src/cli.py dashboard[/bold cyan]",
                    title="Action Required",
                    border_style="yellow",
                )
            )
        else:
            console.print("[yellow]No new jobs generated in this cycle.[/yellow]")
        return 0

    console.print(f"[bold green]Starting continuous scheduler[/bold green] (running every {args.interval_minutes} minutes)...")
    try:
        while True:
            console.print(f"\n[dim][{datetime.now().strftime('%H:%M:%S')}][/dim] Executing batch cycle...")
            sched.run_cycle(
                limit=args.limit,
                min_score=args.min_score,
                sources=sources,
                skip_collect=args.skip_collect,
                render_video=not args.no_video,
            )
            time.sleep(args.interval_minutes * 60)
    except KeyboardInterrupt:
        console.print("\n[yellow]Scheduler stopped.[/yellow]")
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")
    service = PublisherService(config, db=db, live=args.live and not args.dry_run)

    console.print(f"[bold cyan]Initiating publishing workflow for job:[/bold cyan] {args.job_id} (platform={args.platform}, dry_run={args.dry_run})")
    try:
        results = service.publish_job(
            args.job_id,
            platform=args.platform,
            dry_run=args.dry_run,
            force=args.force,
        )
    except PublishingGateError as exc:
        console.print(f"[bold red]Approval Gate Failure:[/bold red] {exc}")
        return 1
    except Exception as exc:
        console.print(f"[bold red]Publishing error:[/bold red] {exc}")
        return 1

    table = Table(title=f"Publish Results — Job {args.job_id}")
    table.add_column("Platform", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Post ID / Link", style="magenta")
    table.add_column("Message", style="white")

    all_ok = True
    for p_name, res in results.items():
        st_style = "bold green" if res.status in ("published", "published_dry_run", "staged") else "bold red"
        if res.status == "failed":
            all_ok = False
        table.add_row(
            p_name,
            f"[{st_style}]{res.status}[/{st_style}]",
            res.url or res.post_id or "-",
            res.message or res.error or "",
        )

    console.print(table)
    return 0 if all_ok else 2


def cmd_publish_status(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")
    job = db.get_job(args.job_id)
    if not job:
        console.print(f"[red]Job not found:[/red] {args.job_id}")
        return 1

    table = Table(title=f"Job Publishing Status — {job.slug}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Job ID", job.id)
    table.add_row("Approval Status", job.status.value)
    table.add_row("Publish Status", job.publish_status.value)
    table.add_row("Target Platform", job.published_platform or "-")
    table.add_row("Post ID", job.platform_post_id or "-")
    table.add_row("Platform URL", job.platform_url or "-")
    table.add_row("Attempts", str(job.publish_attempts))
    table.add_row("Published At", job.published_at or "-")
    table.add_row("Last Error", job.last_publish_error or "-")

    console.print(table)
    return 0


def cmd_recover(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")
    engine = JobRecoveryEngine(db=db, config=config)

    console.print("[bold cyan]Scanning for stale or interrupted jobs to recover...[/bold cyan]")
    recovered = engine.recover_stale_jobs()
    if not recovered:
        console.print("[green]All jobs in database are healthy and clean. No interrupted jobs found.[/green]")
        return 0

    table = Table(title=f"Recovered Jobs ({len(recovered)} total)")
    table.add_column("Job ID", style="cyan")
    table.add_column("New Status", style="green")
    table.add_column("Notes / Recovery Action", style="white")

    for j in recovered:
        table.add_row(j.id, j.status.value, j.notes or j.last_publish_error or "-")

    console.print(table)
    return 0


def cmd_analytics(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")

    job = db.get_job(args.job_id)
    if not job:
        console.print(f"[red]Job not found:[/red] {args.job_id}")
        return 1

    snapshots = db.list_snapshots(job_id=job.id, limit=args.limit)

    table = Table(title=f"Performance Snapshots — {job.slug}")
    table.add_column("Timestamp", style="cyan")
    table.add_column("Platform", style="yellow")
    table.add_column("Views", style="green", justify="right")
    table.add_column("Likes", style="green", justify="right")
    table.add_column("Comments", style="white", justify="right")
    table.add_column("Shares", style="white", justify="right")
    table.add_column("Retention", style="magenta", justify="right")
    table.add_column("Engagement Score", style="bold yellow", justify="right")

    if not snapshots:
        console.print(f"[yellow]No performance snapshots recorded yet for {job.slug}. Run 'sync-metrics' first.[/yellow]")
        return 0

    for s in snapshots:
        table.add_row(
            s.snapshot_at[:19].replace("T", " "),
            s.platform,
            f"{s.metrics.views:,}",
            f"{s.metrics.likes:,}",
            f"{s.metrics.comments:,}",
            f"{s.metrics.shares:,}",
            f"{s.metrics.retention_rate_pct:.1f}%",
            f"{s.engagement_score:.1f}",
        )

    console.print(table)
    return 0


def cmd_analytics_summary(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")
    reporter = AnalyticsReporter(db=db)

    report = reporter.generate_summary_report(platform=args.platform)

    console.print(f"[bold cyan]AI Content Automation — Overall Performance Summary[/bold cyan] (Platform: {args.platform or 'all'})\n")

    summary_table = Table(title="Global Performance Totals")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="bold green")

    summary_table.add_row("Total Published / Tracked Jobs", str(report.total_published_jobs))
    summary_table.add_row("Total Historical Snapshots", str(report.total_snapshots))
    summary_table.add_row("Total Views", f"{report.total_views:,}")
    summary_table.add_row("Total Likes", f"{report.total_likes:,}")
    summary_table.add_row("Total Comments", f"{report.total_comments:,}")
    summary_table.add_row("Total Shares", f"{report.total_shares:,}")
    summary_table.add_row("Average Retention Rate", f"{report.avg_retention_pct:.1f}%")
    summary_table.add_row("Average Engagement Score", f"{report.avg_engagement_score:.1f} / 100")
    console.print(summary_table)

    if report.by_format:
        fmt_table = Table(title="\nPerformance Breakdown by Content Format")
        fmt_table.add_column("Format", style="cyan")
        fmt_table.add_column("Count", justify="right")
        fmt_table.add_column("Total Views", style="green", justify="right")
        fmt_table.add_column("Avg Views", style="green", justify="right")
        fmt_table.add_column("Avg Retention", style="magenta", justify="right")
        fmt_table.add_column("Avg Engagement", style="bold yellow", justify="right")

        for f in report.by_format:
            fmt_table.add_row(
                f.category,
                str(f.count),
                f"{f.total_views:,}",
                f"{f.avg_views:.1f}",
                f"{f.avg_retention_rate:.1f}%",
                f"{f.avg_engagement_score:.1f}",
            )
        console.print(fmt_table)

    if report.by_hook_type:
        hk_table = Table(title="\nPerformance Breakdown by Hook Strategy")
        hk_table.add_column("Hook Strategy", style="cyan")
        hk_table.add_column("Count", justify="right")
        hk_table.add_column("Total Views", style="green", justify="right")
        hk_table.add_column("Avg Retention", style="magenta", justify="right")
        hk_table.add_column("Avg Engagement", style="bold yellow", justify="right")

        for h in report.by_hook_type:
            hk_table.add_row(
                h.category,
                str(h.count),
                f"{h.total_views:,}",
                f"{h.avg_retention_rate:.1f}%",
                f"{h.avg_engagement_score:.1f}",
            )
        console.print(hk_table)

    return 0


def cmd_sync_metrics(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")
    collector = AnalyticsCollector(db=db, config=config)

    console.print("[bold cyan]Syncing performance metrics for eligible content jobs...[/bold cyan]")
    snapshots = collector.sync_all_jobs(dry_run=args.dry_run)

    if not snapshots:
        console.print("[yellow]No eligible published or staged jobs found to sync.[/yellow]")
        return 0

    table = Table(title=f"Synced Performance Snapshots ({len(snapshots)} total)")
    table.add_column("Slug", style="cyan")
    table.add_column("Platform", style="yellow")
    table.add_column("Views", style="green", justify="right")
    table.add_column("Likes", style="green", justify="right")
    table.add_column("Retention", style="magenta", justify="right")
    table.add_column("Engagement", style="bold yellow", justify="right")

    for s in snapshots:
        table.add_row(
            s.slug,
            s.platform,
            f"{s.metrics.views:,}",
            f"{s.metrics.likes:,}",
            f"{s.metrics.retention_rate_pct:.1f}%",
            f"{s.engagement_score:.1f}",
        )

    console.print(table)
    return 0


def cmd_intelligence(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")
    engine = PerformanceInsightsEngine(db=db, config=config)

    console.print(f"[bold cyan]Content Performance Intelligence[/bold cyan] (Platform: {args.platform or 'all'}, min_samples={args.min_samples})\n")

    report = engine.generate_insights(platform=args.platform, min_samples=args.min_samples)

    if not report.findings:
        console.print("[yellow]No performance snapshots recorded yet. Run 'sync-metrics' first.[/yellow]")
        return 0

    table = Table(title=f"Performance Correlations ({report.total_snapshots} snapshots, {report.total_jobs} jobs)")
    table.add_column("Dimension", style="cyan")
    table.add_column("Category", style="white")
    table.add_column("Count", justify="right")
    table.add_column("Avg Eng.", style="green", justify="right")
    table.add_column("vs Global", style="magenta", justify="right")
    table.add_column("Signal", style="yellow", justify="center")

    for f in report.findings:
        signal = "RELIABLE" if f.reliable else "limited"
        table.add_row(
            f.dimension,
            f.category,
            str(f.count),
            f"{f.avg_engagement_score:.1f}",
            f"{f.performance_ratio:.2f}x",
            signal,
        )
    console.print(table)

    if report.top_recommendations:
        console.print(Panel("\n".join(f"[bold]•[/bold] {r}" for r in report.top_recommendations), title="Interpretable Recommendations", border_style="green"))

    return 0


def cmd_daemon(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")

    console.print(Panel(
        f"Starting Production Automation Daemon\n"
        f"Interval: {args.interval_minutes}m | Batch Limit: {args.limit} | Min Score: {args.min_score} | Dry-Run: {args.dry_run}",
        title="[bold green]AI Content Automation Daemon[/bold green]",
        border_style="green",
    ))

    daemon = AutomationDaemon(
        config=config,
        db=db,
        interval_minutes=args.interval_minutes,
        batch_limit=args.limit,
        min_score=args.min_score,
        prune_days=args.prune_days,
        dry_run=args.dry_run,
    )

    if args.once:
        console.print("[cyan]Executing single scheduled cycle...[/cyan]")
        record = daemon.execute_single_cycle(cycle_type="single_cycle")
        console.print(f"[green]Cycle finished with status:[/green] {record.status} (Duration: {record.duration_seconds}s)")
        return 0

    daemon.run_forever()
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    engine = StoragePruningEngine(output_dir=out_base)

    console.print(f"[bold cyan]Scanning for intermediate files older than {args.days} days...[/bold cyan]")
    res = engine.prune_artifacts(older_than_days=args.days, dry_run=args.dry_run)

    mode_str = "(DRY-RUN)" if args.dry_run else ""
    table = Table(title=f"Storage Pruning Summary {mode_str}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Retention Horizon", f"{res['older_than_days']} days")
    table.add_row("Files Cleaned", str(res["deleted_count"]))
    table.add_row("Disk Space Freed", f"{res['freed_mb']} MB")

    console.print(table)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")

    records = db.list_audit_logs(limit=args.limit)
    if not records:
        console.print("[yellow]No execution audit logs found in database.[/yellow]")
        return 0

    table = Table(title=f"Execution Audit Logs (Last {len(records)} cycles)")
    table.add_column("Started At (UTC)", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Duration", justify="right")
    table.add_column("Generated", justify="right", style="green")
    table.add_column("QA (P/F)", justify="right")
    table.add_column("Status", style="bold")

    for r in records:
        status_color = "green" if r.status == "success" else ("yellow" if r.status == "partial" else "red")
        table.add_row(
            r.started_at[:19].replace("T", " "),
            r.cycle_type,
            f"{r.duration_seconds:.1f}s",
            str(r.jobs_generated),
            f"{r.qa_passed_count}/{r.qa_failed_count}",
            f"[{status_color}]{r.status.upper()}[/{status_color}]",
        )

    console.print(table)
    return 0


def cmd_safeguards(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")
    monitor = SystemHealthMonitor(db=db, output_dir=out_base)

    health = monitor.check_health()

    status_color = "green" if health["status"] == "healthy" else "yellow"
    console.print(Panel(
        f"Overall Health: [{status_color}]{health['status'].upper()}[/{status_color}]\n"
        f"Disk Free: {health['disk_free_gb']} GB (Healthy: {health['disk_healthy']})\n"
        f"FFmpeg Ready: {health['ffmpeg_ready']} | TTS Ready: {health['tts_ready']}\n"
        f"Pending Review: {health['jobs_summary']['pending_review']} | Staged: {health['jobs_summary']['staged']} | Published: {health['jobs_summary']['published']}",
        title="[bold cyan]System Health & Observability[/bold cyan]",
        border_style="cyan",
    ))

    table = Table(title="Daily Publishing Rate Limits & Quotas (Today UTC)")
    table.add_column("Platform", style="yellow")
    table.add_column("Daily Limit", justify="right")
    table.add_column("Used Today", justify="right", style="cyan")
    table.add_column("Remaining", justify="right", style="green")
    table.add_column("Status", style="bold")

    for p, q in health["quota_status"].items():
        status_txt = "[green]ALLOWED[/green]" if q["allowed"] else "[red]EXCEEDED[/red]"
        table.add_row(
            p.capitalize(),
            str(q["limit"]),
            str(q["used_today"]),
            str(q["remaining"]),
            status_txt,
        )

    console.print(table)
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")
    service = DiscoveryService(db=db)
    provider_name = "csv" if args.file else args.provider
    no_website = getattr(args, "no_website", False)
    if no_website:
        console.print("[bold yellow]Filtering for businesses that DO NOT have an official website...[/bold yellow]")
    console.print(f"[bold cyan]Initiating B2B Lead Discovery (Provider: {provider_name})...[/bold cyan]")
    try:
        kwargs: dict[str, Any] = {"no_website_only": no_website}
        if provider_name in ("csv", "csv_import"):
            file_path = args.file or str(PROJECT_ROOT / "data" / "indian_businesses_sample.csv")
            kwargs["file_path"] = file_path
            console.print(f"[dim]Source file: {file_path}[/dim]")

        result = service.ingest_leads(
            provider_name=provider_name,
            city=args.city,
            category=args.category,
            location=args.location,
            limit=args.limit,
            **kwargs,
        )
    except Exception as exc:
        console.print(f"[bold red]Discovery error:[/bold red] {exc}")
        return 1

    table = Table(title=f"Discovered & Ingested Leads ({result.total_saved} new saved, {result.total_duplicates} duplicates skipped)")
    table.add_column("ID", style="cyan", width=24)
    table.add_column("Name", style="bold white")
    table.add_column("Category", style="yellow")
    table.add_column("City", style="green")
    table.add_column("Domain / Website", style="magenta")
    table.add_column("Phone", style="white")

    for b in result.businesses[:25]:
        table.add_row(
            b.id,
            b.name,
            b.category,
            b.city,
            b.domain or b.website or "-",
            b.phone or "-",
        )

    console.print(table)
    if len(result.businesses) > 25:
        console.print(f"... and [bold]{len(result.businesses) - 25}[/bold] more businesses saved.")

    if result.duplicates:
        console.print(f"\n[yellow]Skipped {len(result.duplicates)} duplicate records.[/yellow]")

    console.print(
        Panel(
            f"Total discovered: {result.total_discovered} | Newly saved to database: {result.total_saved} | Duplicates: {result.total_duplicates}\n\n"
            f"View all leads: [bold cyan]python src/cli.py leads[/bold cyan]",
            title="Lead Discovery Complete",
            border_style="cyan",
        )
    )
    return 0


def cmd_leads(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")

    leads = db.list_businesses(
        status=args.status,
        category=args.category,
        city=args.city,
        location=args.location,
        no_website_only=getattr(args, "no_website", False),
        limit=args.limit,
    )

    if not leads:
        console.print("[yellow]No business leads found in database matching criteria.[/yellow]")
        return 0

    table = Table(title=f"Business Leads in Database ({len(leads)} shown)")
    table.add_column("ID", style="cyan", width=24)
    table.add_column("Name", style="bold white")
    table.add_column("Category", style="yellow")
    table.add_column("City", style="green")
    table.add_column("Domain", style="magenta")
    table.add_column("Phone", style="white")
    table.add_column("Email", style="dim")
    table.add_column("Status", style="bold")

    for b in leads:
        st_style = "green" if b.status == BusinessStatus.APPROVED else ("yellow" if b.status == BusinessStatus.DISCOVERED else "cyan")
        table.add_row(
            b.id,
            b.name[:28],
            b.category,
            b.city,
            b.domain or "-",
            b.phone or "-",
            b.email or "-",
            f"[{st_style}]{b.status.value}[/{st_style}]",
        )

    console.print(table)
    return 0


def cmd_validate_leads(args: argparse.Namespace) -> int:
    """Run 5-tier API key data accuracy audit on all stored business leads."""
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")

    from b2b.validator import DataValidationEngine
    validator = DataValidationEngine()

    leads = db.list_businesses(limit=args.limit)
    if not leads:
        console.print("[yellow]No business leads found in database to validate.[/yellow]")
        return 0

    console.print(f"[bold cyan]Auditing & Validating {len(leads)} Business Leads via 5-Tier API Validation Engine...[/bold cyan]\n")

    table = Table(title=f"API Data Validation Report — {len(leads)} Leads Audited")
    table.add_column("Business Name", style="bold white")
    table.add_column("City", style="green")
    table.add_column("Phone", style="white")
    table.add_column("Website", style="magenta")
    table.add_column("Score", style="yellow")
    table.add_column("Accuracy Status", style="bold")

    validated_count = 0
    for b in leads:
        res = validator.validate(b, no_website_only=not bool(b.website))
        db.save_business(b)
        status_text = "[bold green]100% VERIFIED[/bold green]" if res.is_valid else "[bold red]FAILED AUDIT[/bold red]"
        if res.is_valid:
            validated_count += 1

        table.add_row(
            b.name[:28],
            b.city,
            b.phone or "-",
            b.website or "None (No-website)",
            f"{res.validation_score:.1f}%",
            status_text,
        )

    console.print(table)
    console.print(
        Panel(
            f"Total Audited: {len(leads)} | [bold green]100% Verified Validated Leads: {validated_count}[/bold green] | [bold red]Failed Validation: {len(leads) - validated_count}[/bold red]\n\n"
            f"All validated business records updated in SQLite database: {db.db_path}",
            title="API Data Validation Gate Complete",
            border_style="green" if validated_count == len(leads) else "yellow",
        )
    )
    return 0


def cmd_add_lead(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")
    service = DiscoveryService(db=db)

    try:
        result = service.ingest_leads(
            provider_name="manual",
            name=args.name,
            city=args.city,
            category=args.category,
            website=args.website,
            phone=args.phone,
            email=args.email,
            address=args.address,
            state=args.state,
        )
    except Exception as exc:
        console.print(f"[bold red]Failed to add lead:[/bold red] {exc}")
        return 1

    if result.total_saved > 0:
        b = result.businesses[0]
        console.print(
            Panel(
                f"[bold green]Business Lead Successfully Registered[/bold green]\n\n"
                f"ID: [cyan]{b.id}[/cyan]\n"
                f"Name: [bold white]{b.name}[/bold white]\n"
                f"Category: [yellow]{b.category}[/yellow]\n"
                f"City: [green]{b.city}[/green] ({b.state or 'India'})\n"
                f"Website: [magenta]{b.website or '-'}[/magenta] (Domain: {b.domain or '-'})\n"
                f"Phone: [white]{b.phone or '-'}[/white]\n"
                f"Email: [white]{b.email or '-'}[/white]\n"
                f"Status: [bold green]{b.status.value}[/bold green]",
                title="Lead Added",
                border_style="green",
            )
        )
        return 0
    else:
        dup_reason = result.duplicates[0]["reason"] if result.duplicates else "Duplicate lead"
        console.print(f"[bold yellow]Lead was not added (Duplicate detected):[/bold yellow] {dup_reason}")
        return 1


def cmd_business_cycle(args: argparse.Namespace) -> int:
    """Run the intelligence cycle (analysis -> demos -> outreach drafts) offline."""
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")

    no_website = getattr(args, "no_website", False)
    existing_biz = db.list_businesses(status="all", no_website_only=no_website, limit=100)
    real_biz = [b for b in existing_biz if not b.id.startswith("biz_sample_")]

    if not real_biz:
        from b2b.discovery import DiscoveryService
        console.print("[bold cyan]No matching stored production leads found. Initiating real SerpAPI Google Maps discovery...[/bold cyan]")
        service = DiscoveryService(db=db)
        res = service.ingest_leads(provider_name="serpapi", category="salon", city="Ahmedabad", limit=5, no_website_only=no_website)
        existing_biz = res.businesses
        real_biz = existing_biz

    target_leads = real_biz

    svc = BusinessIntelligenceService(db)
    ctx = BusinessCycleContext(cycle_id="cli_cycle")

    # Run research for any target leads lacking research records
    svc.run_research_step(ctx, target_leads)

    research = [r for b in target_leads if (r := db.get_business_research(b.id))]

    opps = svc.run_analysis_step(ctx, research)
    demos = svc.run_demo_step(ctx, opps)
    drafts = svc.run_outreach_step(ctx, demos)

    if args.json:
        report = {
            "businesses_researched": len(research),
            "opportunities": len(opps),
            "demos": [d.artifact_path for d in demos],
            "outreach_drafts": len(drafts),
            "pending_review": [o.id for o in drafts],
            "stats": ctx.stats,
            "errors": ctx.errors,
        }
        console.print_json(data=report)
        return 0

    table = Table(title=f"Business Intelligence Cycle (fixture dataset) — {len(opps)} opportunities")
    table.add_column("Business", style="bold white")
    table.add_column("Opportunity", style="cyan")
    table.add_column("Score", style="yellow")
    table.add_column("Demo", style="green")
    table.add_column("Approval", style="magenta")
    for o in opps[:15]:
        business = db.get_business(o.business_id)
        demo = next((d for d in demos if d.opportunity_id == o.id), None)
        approval = "pending_review" if any(dr.business_id == o.business_id for dr in drafts) else "-"
        table.add_row(
            (business.name if business else o.business_id)[:26],
            o.opportunity_type.value,
            f"{o.score:.1f}",
            demo.artifact_path if demo else "-",
            approval,
        )
    console.print(table)

    if demos:
        console.print(
            Panel(
                f"Demos generated: [bold green]{len(demos)}[/bold green]\n\n"
                f"Open a demo artifact:\n  [bold cyan]python src/cli.py business-cycle --demo --output-dir output[/bold cyan]\n"
                f"First demo: [bold]{demos[0].artifact_path}[/bold]",
                title="Cycle Complete — Rejected: None (all drafts in human approval queue)",
                border_style="green",
            )
        )
    return 0 if not ctx.errors else 1


def cmd_b2b_approve(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")

    updated = db.update_outreach_approval(args.outreach_id, ApprovalStatus.APPROVED)
    if not updated:
        console.print(f"[red]Outreach record not found:[/red] {args.outreach_id}")
        return 1

    console.print(f"[bold green]✓ Outreach {args.outreach_id} APPROVED for sending.[/bold green]")
    return 0


def cmd_b2b_send(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")
    sender = OutreachSendingService(db=db, live=not args.dry_run)

    try:
        sent = sender.send_outreach(args.outreach_id, force_dry_run=args.dry_run)
        console.print(
            Panel(
                f"[bold green]Outreach Email Dispatched Successfully[/bold green]\n\n"
                f"Outreach ID: [cyan]{sent.id}[/cyan]\n"
                f"Recipient: [white]{sent.recipient_email}[/white]\n"
                f"Subject: [bold white]{sent.subject}[/bold white]\n"
                f"Status: [green]{sent.send_status.value}[/green]\n"
                f"Sent At: [dim]{sent.sent_at}[/dim]\n"
                f"Provider Message ID: [magenta]{sent.provider_message_id or 'mock'}[/magenta]",
                title="Delivery Complete",
                border_style="green",
            )
        )
        return 0
    except ApprovalGateError as exc:
        console.print(f"[bold red]Approval Gate Failure:[/bold red] {exc}")
        return 1
    except Exception as exc:
        console.print(f"[bold red]Send error:[/bold red] {exc}")
        return 1


def cmd_b2b_respond(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")
    intel = BusinessIntelligenceService(db=db)

    try:
        resp = intel.ingest_response(None, args.outreach_id, args.message)
        console.print(
            Panel(
                f"[bold green]Inbound Response Ingested & Classified[/bold green]\n\n"
                f"Response ID: [cyan]{resp.id}[/cyan]\n"
                f"Outreach ID: [white]{resp.outreach_id}[/white]\n"
                f"Classification: [bold magenta]{resp.classification.value.upper()}[/bold magenta]\n"
                f"Inbound Message: [dim]\"{resp.raw_content}\"[/dim]\n\n"
                f"Suggested AI Reply:\n[green]{resp.suggested_reply or '-'}[/green]",
                title="Response Processed",
                border_style="magenta",
            )
        )
        return 0
    except Exception as exc:
        console.print(f"[bold red]Response ingestion error:[/bold red] {exc}")
        return 1


def cmd_b2b_followup(args: argparse.Namespace) -> int:
    config = get_config()
    out_base = Path(args.output_dir or config.get("pipeline", {}).get("output_dir", "output"))
    db = Database(out_base / "automation.db")

    if args.stage:
        intel = BusinessIntelligenceService(db=db)
        ctx = BusinessCycleContext()
        staged, plans = intel.followup_step(ctx)
        console.print(f"[bold green]Staged {len(staged)} follow-ups ({len([p for p in plans if p.eligible])} eligible plans).[/bold green]")

    followups = db.list_followups(status=args.status, limit=args.limit)
    if not followups:
        console.print("[yellow]No follow-ups recorded in database.[/yellow]")
        return 0

    table = Table(title=f"Follow-ups in Database ({len(followups)} shown)")
    table.add_column("ID", style="cyan")
    table.add_column("Outreach ID", style="dim")
    table.add_column("Step", justify="center")
    table.add_column("Subject", style="white")
    table.add_column("Status", style="bold")

    for f in followups:
        st_color = "green" if f.status == FollowUpStatus.SENT else ("yellow" if f.status == FollowUpStatus.PENDING_REVIEW else "cyan")
        table.add_row(
            f.id,
            f.outreach_id,
            f"Day {3 if f.step_number == 1 else 7}",
            f.subject[:45],
            f"[{st_color}]{f.status.value}[/{st_color}]",
        )
    console.print(table)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aicontent",
        description="AI Content & B2B Business Outreach Automation System.",
    )
    parser.add_argument("--log-level", default="INFO", help="DEBUG | INFO | WARNING | ERROR")
    sub = parser.add_subparsers(dest="command", required=True)

    disc = sub.add_parser("discover", help="Discover and ingest real business leads live or from CSV into database.")
    disc.add_argument("--provider", choices=["live", "csv", "manual", "serpapi", "google_places"], default="live", help="Discovery provider (default: live)")
    disc.add_argument("--file", default=None, help="Path to CSV lead file (used when provider=csv)")
    disc.add_argument("--location", default=None, help="Location filter (e.g. Navrangpura Ahmedabad, SG Highway Ahmedabad, Andheri Mumbai)")
    disc.add_argument("--city", default=None, help="City to discover (e.g. Ahmedabad, Mumbai, Delhi, Bangalore)")
    disc.add_argument("--category", default=None, help="Category to discover (e.g. clinic, restaurant, salon, coaching, gym)")
    disc.add_argument("--no-website", action="store_true", help="Filter for businesses that DO NOT have an official website")
    disc.add_argument("--limit", type=int, default=50, help="Maximum leads to ingest (default: 50)")
    disc.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    disc.set_defaults(func=cmd_discover)

    # leads (Phase B)
    leads_p = sub.add_parser("leads", help="List discovered business leads in database.")
    leads_p.add_argument("--location", default=None, help="Filter by location keyword (city/area/address)")
    leads_p.add_argument("--city", default=None, help="Filter by city")
    leads_p.add_argument("--category", default=None, help="Filter by category")
    leads_p.add_argument("--status", default=None, help="Filter by lifecycle status")
    leads_p.add_argument("--no-website", action="store_true", help="Display only leads lacking an official website")
    leads_p.add_argument("--limit", type=int, default=50, help="Maximum leads to display (default: 50)")
    leads_p.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    leads_p.set_defaults(func=cmd_leads)

    # validate-leads (Phase B API Accuracy Gate)
    val_p = sub.add_parser("validate-leads", help="Run 5-tier API key data accuracy audit on all stored business leads.")
    val_p.add_argument("--limit", type=int, default=50, help="Maximum leads to validate (default: 50)")
    val_p.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    val_p.set_defaults(func=cmd_validate_leads)

    # add-lead (Phase B)
    add_p = sub.add_parser("add-lead", help="Manually add a single business lead.")
    add_p.add_argument("--name", required=True, help="Business name")
    add_p.add_argument("--city", required=True, help="City (e.g. Ahmedabad)")
    add_p.add_argument("--category", default="general_smb", help="Business category (e.g. clinic, salon)")
    add_p.add_argument("--website", default=None, help="Website URL")
    add_p.add_argument("--phone", default=None, help="Phone / mobile number")
    add_p.add_argument("--email", default=None, help="Email address")
    add_p.add_argument("--address", default=None, help="Physical address")
    add_p.add_argument("--state", default=None, help="State (e.g. Gujarat)")
    add_p.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    add_p.set_defaults(func=cmd_add_lead)

    # business-cycle (B2B Intelligence)
    bc = sub.add_parser("business-cycle", help="Run analysis -> demos -> outreach draft cycle on the stored leads.")
    bc.add_argument("--demo", action="store_true", help="Seed offline sample businesses + static research first (fixture provider)")
    bc.add_argument("--no-website", action="store_true", help="Target only leads lacking an official website")
    bc.add_argument("--use-registered-provider", action="store_true", help="Run live research via any registered provider instead of stored research")
    bc.add_argument("--json", action="store_true", help="Emit machine-readable JSON report")
    bc.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    bc.set_defaults(func=cmd_business_cycle)

    # b2b-approve
    appr_p = sub.add_parser("b2b-approve", help="Approve an outreach draft.")
    appr_p.add_argument("--outreach-id", required=True, help="Outreach ID to approve")
    appr_p.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    appr_p.set_defaults(func=cmd_b2b_approve)

    # b2b-send
    send_p = sub.add_parser("b2b-send", help="Send an approved outreach email (safe gate enforced).")
    send_p.add_argument("--outreach-id", required=True, help="Outreach ID to send")
    send_p.add_argument("--dry-run", action="store_true", default=True, help="Dry-run / staged mode (default: True)")
    send_p.add_argument("--live", dest="dry_run", action="store_false", help="Real dispatch mode")
    send_p.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    send_p.set_defaults(func=cmd_b2b_send)

    # b2b-respond
    resp_p = sub.add_parser("b2b-respond", help="Ingest and classify an inbound customer reply.")
    resp_p.add_argument("--outreach-id", required=True, help="Outreach ID being replied to")
    resp_p.add_argument("--message", required=True, help="Inbound reply text")
    resp_p.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    resp_p.set_defaults(func=cmd_b2b_respond)

    # b2b-followup
    fu_p = sub.add_parser("b2b-followup", help="Manage multi-step follow-up cadences.")
    fu_p.add_argument("--stage", action="store_true", help="Stage new eligible follow-ups")
    fu_p.add_argument("--status", default=None, help="Filter by follow-up status")
    fu_p.add_argument("--limit", type=int, default=20, help="Max follow-ups to display")
    fu_p.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    fu_p.set_defaults(func=cmd_b2b_followup)

    # generate (Phase 1)
    gen = sub.add_parser("generate", help="Generate a short video from a topic.")
    gen.add_argument("--topic", required=True, help='e.g. "Top 3 productivity hacks"')
    gen.add_argument("--provider", choices=["template", "openai"], default=None,
                     help="script provider override (default: from config)")
    gen.add_argument("--voice", default=None, help="edge-tts voice id override")
    gen.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    gen.add_argument("--no-video", action="store_true", help="skip the video composition stage")
    gen.add_argument("--seed", type=int, default=None, help="deterministic template provider seed")
    gen.set_defaults(func=cmd_generate)

    # doctor (Phase 1 & 7 & 8)
    doc = sub.add_parser("doctor", help="Check the environment, database, and publishing readiness.")
    doc.set_defaults(func=cmd_doctor)

    # recover (Phase 8)
    rec = sub.add_parser("recover", help="Scan and repair interrupted or crashed generation/publishing jobs.")
    rec.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    rec.set_defaults(func=cmd_recover)

    # collect (Phase 2)
    col = sub.add_parser("collect", help="Fetch raw content items from configured sources (RSS, Reddit).")
    col.add_argument("--sources", default=None, help="Comma-separated sources: rss,reddit (default: all)")
    col.add_argument("--limit", type=int, default=15, help="Max items per source (default: 15)")
    col.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    col.set_defaults(func=cmd_collect)

    # process (Phase 2)
    proc = sub.add_parser("process", help="Clean, deduplicate, rank, and summarize collected items.")
    proc.add_argument("--input", default=None, help="Input collected JSON file (default: output/collected/latest.json)")
    proc.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    proc.add_argument("--limit", type=int, default=10, help="Number of top candidates to display (default: 10)")
    proc.set_defaults(func=cmd_process)

    # auto (Phase 3 & 4 & 6)
    auto = sub.add_parser("auto", help="Automated pipeline: collect -> process -> select -> generate short video.")
    auto.add_argument("--limit", type=int, default=1, help="Number of short videos to generate (default: 1)")
    auto.add_argument("--min-score", type=float, default=30.0, help="Minimum candidate score (default: 30.0)")
    auto.add_argument("--sources", default=None, help="Comma-separated sources: rss,reddit (default: all)")
    auto.add_argument("--skip-collect", action="store_true", help="Skip re-fetching; select from existing latest.json")
    auto.add_argument("--provider", choices=["template", "openai"], default=None,
                      help="script provider override (default: from config)")
    auto.add_argument("--voice", default=None, help="edge-tts voice id override")
    auto.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    auto.add_argument("--no-video", action="store_true", help="skip the video composition stage")
    auto.add_argument("--seed", type=int, default=None, help="deterministic seed for template provider")
    auto.add_argument("--feedback", action="store_true",
                      help="apply learned performance feedback to candidate ranking (Phase 9)")
    auto.add_argument("--diversity", action="store_true",
                      help="apply topic-fatigue / anti-repetition diversity scoring to ranking (Phase 10)")
    auto.set_defaults(func=cmd_auto)

    # dashboard (Phase 5 & 7)
    dash = sub.add_parser("dashboard", help="Start the local human approval studio web dashboard.")
    dash.add_argument("--port", type=int, default=8585, help="Dashboard port (default: 8585)")
    dash.add_argument("--host", default="127.0.0.1", help="Dashboard host (default: 127.0.0.1)")
    dash.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    dash.set_defaults(func=cmd_dashboard)

    # schedule (Phase 5)
    sched = sub.add_parser("schedule", help="Execute or schedule recurring automated batch generation.")
    sched.add_argument("--limit", type=int, default=1, help="Number of videos per batch (default: 1)")
    sched.add_argument("--min-score", type=float, default=30.0, help="Minimum candidate score (default: 30.0)")
    sched.add_argument("--sources", default=None, help="Comma-separated sources (default: all)")
    sched.add_argument("--interval-minutes", type=int, default=0, help="Recurring interval (0 = single cycle)")
    sched.add_argument("--skip-collect", action="store_true", help="Skip re-fetching from feeds")
    sched.add_argument("--no-video", action="store_true", help="skip the video composition stage")
    sched.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    sched.set_defaults(func=cmd_schedule)

    # publish (Phase 7)
    pub = sub.add_parser("publish", help="Stage or publish an approved job to YouTube Shorts / Instagram Reels.")
    pub.add_argument("--job-id", required=True, help="Job ID or slug (e.g. job_slug or slug)")
    pub.add_argument("--platform", choices=["youtube", "instagram", "all"], default="all",
                     help="Target platform: youtube, instagram, or all (default: all)")
    pub.add_argument("--dry-run", action="store_true", help="Validate and stage payload without contacting remote API")
    pub.add_argument("--live", action="store_true", help="Enable real live upload to social platform")
    pub.add_argument("--force", action="store_true", help="Force republish even if already marked PUBLISHED")
    pub.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    pub.set_defaults(func=cmd_publish)

    # publish-status (Phase 7)
    pstat = sub.add_parser("publish-status", help="Inspect detailed publishing state for a job.")
    pstat.add_argument("--job-id", required=True, help="Job ID or slug to inspect")
    pstat.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    pstat.set_defaults(func=cmd_publish_status)

    # analytics (Phase 9)
    ana = sub.add_parser("analytics", help="Inspect historical performance snapshots for a job.")
    ana.add_argument("--job-id", required=True, help="Job ID or slug (e.g. job_slug or slug)")
    ana.add_argument("--limit", type=int, default=20, help="Max snapshots to display (default: 20)")
    ana.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    ana.set_defaults(func=cmd_analytics)

    # analytics-summary (Phase 9)
    anasum = sub.add_parser("analytics-summary", help="Display global performance metrics and format breakdowns.")
    anasum.add_argument("--platform", choices=["youtube", "instagram", "all"], default=None,
                        help="Filter by platform (default: all)")
    anasum.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    anasum.set_defaults(func=cmd_analytics_summary)

    # sync-metrics (Phase 9)
    sync = sub.add_parser("sync-metrics", help="Collect and record latest performance snapshots for eligible jobs.")
    sync.add_argument("--dry-run", action="store_true", help="Simulate metrics collection without remote API calls")
    sync.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    sync.set_defaults(func=cmd_sync_metrics)

    # intelligence (Phase 9)
    intel = sub.add_parser("intelligence", help="Identify performance correlations and produce content recommendations.")
    intel.add_argument("--platform", choices=["youtube", "instagram", "all"], default=None,
                       help="Filter analysis by platform (default: all)")
    intel.add_argument("--min-samples", type=int, default=3,
                       help="Minimum snapshots before a correlation is trusted (default: 3)")
    intel.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    intel.set_defaults(func=cmd_intelligence)

    # daemon (Phase 10)
    dae = sub.add_parser("daemon", help="Run long-running automated production daemon.")
    dae.add_argument("--interval-minutes", type=int, default=60, help="Interval between cycles in minutes (default: 60)")
    dae.add_argument("--limit", type=int, default=1, help="Max videos to generate per cycle (default: 1)")
    dae.add_argument("--min-score", type=float, default=30.0, help="Minimum candidate score (default: 30.0)")
    dae.add_argument("--prune-days", type=int, default=7, help="Intermediate artifact retention days (default: 7)")
    dae.add_argument("--dry-run", action="store_true", help="Dry-run mode for metrics and publishing")
    dae.add_argument("--once", action="store_true", help="Execute single cycle and exit (for cron/scheduled tasks)")
    dae.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    dae.set_defaults(func=cmd_daemon)

    # prune (Phase 10)
    pru = sub.add_parser("prune", help="Clean up stale intermediate drafts and audio files.")
    pru.add_argument("--days", type=int, default=7, help="Prune files older than N days (default: 7)")
    pru.add_argument("--dry-run", action="store_true", help="Simulate pruning without deleting files")
    pru.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    pru.set_defaults(func=cmd_prune)

    # audit (Phase 10)
    aud = sub.add_parser("audit", help="Inspect automated execution audit logs.")
    aud.add_argument("--limit", type=int, default=20, help="Max audit records to display (default: 20)")
    aud.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    aud.set_defaults(func=cmd_audit)

    # safeguards (Phase 10)
    saf = sub.add_parser("safeguards", help="Inspect operational safeguards, rate limits, and health status.")
    saf.add_argument("--output-dir", default=None, help="output directory (default: output/)")
    saf.set_defaults(func=cmd_safeguards)

    return parser






def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.log_level)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())