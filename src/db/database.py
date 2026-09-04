"""SQLite database manager for persistent job tracking, strategy storage, and production publishing."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone

from pathlib import Path
from typing import Any

from config import PROJECT_ROOT
from analytics.models import PerformanceSnapshot, PlatformMetrics
from db.models import AuditLogRecord, JobRecord, JobStatus, PublishStatus
from b2b.models import (
    ApprovalStatus,
    BusinessRecord,
    BusinessResearch,
    BusinessStatus,
    ClaimType,
    DemoRecord,
    DemoStatus,
    DemoType,
    EvidenceCategory,
    FollowUpRecord,
    FollowUpStatus,
    OpportunityPriority,
    OpportunityRecord,
    OpportunityType,
    OutreachRecord,
    OutreachResponse,
    QualificationStatus,
    ReplyStatus,
    ResearchEvidence,
    ResponseClassification,
    SendStatus,
    SourceType,
    VerticalType,
)

logger = logging.getLogger(__name__)



class Database:
    """Manages SQLite database storage for content jobs, strategy blueprints, and approvals."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            self.db_path = PROJECT_ROOT / "output" / "automation.db"
        else:
            self.db_path = Path(db_path)
            if not self.db_path.is_absolute():
                self.db_path = PROJECT_ROOT / self.db_path

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Initialize SQLite database schema and migrate strategy & publishing columns if needed."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    slug TEXT UNIQUE NOT NULL,
                    topic TEXT NOT NULL,
                    candidate_id TEXT,
                    source_name TEXT,
                    source_url TEXT,
                    status TEXT NOT NULL,
                    score REAL DEFAULT 0.0,
                    quality_score REAL DEFAULT 0.0,
                    quality_passed INTEGER DEFAULT 1,
                    content_format TEXT DEFAULT 'explainer',
                    hook_strategy TEXT DEFAULT 'curiosity_gap',
                    target_audience TEXT DEFAULT 'general_consumers',
                    strategy_json TEXT DEFAULT '{}',
                    script_json TEXT DEFAULT '{}',
                    youtube_title TEXT DEFAULT '',
                    youtube_description TEXT DEFAULT '',
                    youtube_tags TEXT DEFAULT '[]',
                    instagram_caption TEXT DEFAULT '',
                    video_path TEXT,
                    thumbnail_path TEXT,
                    audio_path TEXT,
                    notes TEXT,
                    publish_status TEXT DEFAULT 'not_started',
                    published_platform TEXT,
                    platform_post_id TEXT,
                    platform_url TEXT,
                    published_at TEXT,
                    publish_attempts INTEGER DEFAULT 0,
                    last_publish_error TEXT,
                    publish_response_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    reviewed_at TEXT
                )
                """
            )
            # Ensure migration for existing databases without new columns
            existing_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
            }
            migrations = [
                ("content_format", "TEXT DEFAULT 'explainer'"),
                ("hook_strategy", "TEXT DEFAULT 'curiosity_gap'"),
                ("target_audience", "TEXT DEFAULT 'general_consumers'"),
                ("strategy_json", "TEXT DEFAULT '{}'"),
                ("publish_status", "TEXT DEFAULT 'not_started'"),
                ("published_platform", "TEXT"),
                ("platform_post_id", "TEXT"),
                ("platform_url", "TEXT"),
                ("published_at", "TEXT"),
                ("publish_attempts", "INTEGER DEFAULT 0"),
                ("last_publish_error", "TEXT"),
                ("publish_response_json", "TEXT DEFAULT '{}'"),
                ("latest_views", "INTEGER DEFAULT 0"),
                ("latest_likes", "INTEGER DEFAULT 0"),
                ("latest_engagement_score", "REAL DEFAULT 0.0"),
                ("metrics_updated_at", "TEXT"),
            ]
            for col_name, col_type in migrations:
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")

            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_publish_status ON jobs(publish_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_candidate ON jobs(candidate_id)")

            # Phase 9: Performance Snapshots table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS performance_snapshots (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    post_id TEXT,
                    views INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    watch_time_seconds REAL DEFAULT 0.0,
                    avg_view_duration_seconds REAL DEFAULT 0.0,
                    retention_rate_pct REAL DEFAULT 0.0,
                    impressions INTEGER DEFAULT 0,
                    ctr_pct REAL DEFAULT 0.0,
                    engagement_score REAL DEFAULT 0.0,
                    snapshot_at TEXT NOT NULL,
                    raw_response_json TEXT DEFAULT '{}'
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_job_id ON performance_snapshots(job_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_slug ON performance_snapshots(slug)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_platform ON performance_snapshots(platform)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_snapshot_at ON performance_snapshots(snapshot_at)")

            # Phase 10: Operational Audit Logs table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    cycle_type TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    duration_seconds REAL DEFAULT 0.0,
                    items_collected INTEGER DEFAULT 0,
                    candidates_processed INTEGER DEFAULT 0,
                    jobs_generated INTEGER DEFAULT 0,
                    qa_passed_count INTEGER DEFAULT 0,
                    qa_failed_count INTEGER DEFAULT 0,
                    published_count INTEGER DEFAULT 0,
                    errors_count INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    details_json TEXT DEFAULT '{}'
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_started_at ON audit_logs(started_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_logs(status)")

            # Phase A: B2B Business Discovery, Research, Opportunities, Demos & Outreach Tables
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS businesses (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    city TEXT NOT NULL,
                    state TEXT,
                    country TEXT DEFAULT 'India',
                    address TEXT,
                    website TEXT,
                    domain TEXT,
                    phone TEXT,
                    email TEXT,
                    source_provider TEXT NOT NULL,
                    source_id TEXT,
                    status TEXT NOT NULL DEFAULT 'discovered',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(name, city)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_businesses_domain ON businesses(domain)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_businesses_category ON businesses(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_businesses_city ON businesses(city)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_businesses_status ON businesses(status)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS research_evidence (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                    category TEXT NOT NULL,
                    claim TEXT NOT NULL,
                    claim_type TEXT NOT NULL DEFAULT 'verified_fact',
                    evidence_url TEXT,
                    raw_snippet TEXT,
                    source_type TEXT NOT NULL DEFAULT 'website_homepage',
                    confidence REAL NOT NULL DEFAULT 1.0,
                    collected_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_business ON research_evidence(business_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_category ON research_evidence(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_type ON research_evidence(claim_type)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS business_research (
                    business_id TEXT PRIMARY KEY REFERENCES businesses(id) ON DELETE CASCADE,
                    website_exists INTEGER DEFAULT 0,
                    website_url TEXT,
                    is_mobile_friendly INTEGER,
                    speed_score REAL,
                    tech_stack_json TEXT DEFAULT '[]',
                    services_json TEXT DEFAULT '[]',
                    pricing_info TEXT,
                    contact_methods_json TEXT DEFAULT '[]',
                    social_links_json TEXT DEFAULT '{}',
                    booking_system_found INTEGER DEFAULT 0,
                    ordering_system_found INTEGER DEFAULT 0,
                    observed_weaknesses_json TEXT DEFAULT '[]',
                    observed_strengths_json TEXT DEFAULT '[]',
                    researched_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS opportunities (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                    opportunity_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    problem_summary TEXT NOT NULL,
                    proposed_solution TEXT NOT NULL,
                    business_value TEXT NOT NULL,
                    score REAL NOT NULL,
                    score_reasons_json TEXT DEFAULT '[]',
                    risks_json TEXT DEFAULT '[]',
                    confidence REAL DEFAULT 1.0,
                    priority TEXT DEFAULT 'medium',
                    qualification_status TEXT DEFAULT 'qualified',
                    evidence_ids_json TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'identified',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_opps_business ON opportunities(business_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_opps_type ON opportunities(opportunity_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_opps_score ON opportunities(score)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS demos (
                    id TEXT PRIMARY KEY,
                    opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
                    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                    vertical TEXT NOT NULL DEFAULT 'general_smb',
                    demo_type TEXT NOT NULL DEFAULT 'landing_page',
                    title TEXT NOT NULL,
                    artifact_path TEXT NOT NULL,
                    preview_url TEXT,
                    status TEXT DEFAULT 'ready',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_demos_business ON demos(business_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_demos_opp ON demos(opportunity_id)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outreach (
                    id TEXT PRIMARY KEY,
                    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                    opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
                    demo_id TEXT REFERENCES demos(id),
                    recipient_email TEXT NOT NULL,
                    recipient_name TEXT,
                    subject TEXT NOT NULL,
                    body_text TEXT NOT NULL,
                    body_html TEXT,
                    followup_body TEXT,
                    personalization_reasons_json TEXT DEFAULT '[]',
                    evidence_used_json TEXT DEFAULT '[]',
                    approval_status TEXT NOT NULL DEFAULT 'pending_review',
                    send_status TEXT NOT NULL DEFAULT 'draft',
                    sent_at TEXT,
                    provider_message_id TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_outreach_business ON outreach(business_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_outreach_opp ON outreach(opportunity_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_outreach_approval ON outreach(approval_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_outreach_send ON outreach(send_status)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outreach_responses (
                    id TEXT PRIMARY KEY,
                    outreach_id TEXT NOT NULL REFERENCES outreach(id) ON DELETE CASCADE,
                    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                    received_at TEXT NOT NULL,
                    classification TEXT NOT NULL DEFAULT 'unclear',
                    raw_content TEXT NOT NULL,
                    suggested_reply TEXT,
                    reply_status TEXT NOT NULL DEFAULT 'pending_review'
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_outreach ON outreach_responses(outreach_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_business ON outreach_responses(business_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_responses_class ON outreach_responses(classification)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS followups (
                    id TEXT PRIMARY KEY,
                    outreach_id TEXT NOT NULL REFERENCES outreach(id) ON DELETE CASCADE,
                    business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                    step_number INTEGER NOT NULL DEFAULT 1,
                    scheduled_date TEXT,
                    subject TEXT NOT NULL,
                    body_text TEXT NOT NULL,
                    body_html TEXT,
                    status TEXT NOT NULL DEFAULT 'pending_review',
                    sent_at TEXT,
                    provider_message_id TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_followups_outreach ON followups(outreach_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_followups_business ON followups(business_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_followups_status ON followups(status)")

            conn.commit()




    def save_job(self, job: JobRecord) -> JobRecord:
        """Insert or replace a job record."""
        now = datetime.now(timezone.utc).isoformat()
        job.updated_at = now
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, slug, topic, candidate_id, source_name, source_url, status,
                    score, quality_score, quality_passed, content_format, hook_strategy,
                    target_audience, strategy_json, script_json,
                    youtube_title, youtube_description, youtube_tags, instagram_caption,
                    video_path, thumbnail_path, audio_path, notes,
                    publish_status, published_platform, platform_post_id, platform_url,
                    published_at, publish_attempts, last_publish_error, publish_response_json,
                    latest_views, latest_likes, latest_engagement_score, metrics_updated_at,
                    created_at, updated_at, reviewed_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?
                )
                ON CONFLICT(id) DO UPDATE SET
                    slug=excluded.slug,
                    topic=excluded.topic,
                    candidate_id=excluded.candidate_id,
                    source_name=excluded.source_name,
                    source_url=excluded.source_url,
                    status=excluded.status,
                    score=excluded.score,
                    quality_score=excluded.quality_score,
                    quality_passed=excluded.quality_passed,
                    content_format=excluded.content_format,
                    hook_strategy=excluded.hook_strategy,
                    target_audience=excluded.target_audience,
                    strategy_json=excluded.strategy_json,
                    script_json=excluded.script_json,
                    youtube_title=excluded.youtube_title,
                    youtube_description=excluded.youtube_description,
                    youtube_tags=excluded.youtube_tags,
                    instagram_caption=excluded.instagram_caption,
                    video_path=excluded.video_path,
                    thumbnail_path=excluded.thumbnail_path,
                    audio_path=excluded.audio_path,
                    notes=excluded.notes,
                    publish_status=excluded.publish_status,
                    published_platform=excluded.published_platform,
                    platform_post_id=excluded.platform_post_id,
                    platform_url=excluded.platform_url,
                    published_at=excluded.published_at,
                    publish_attempts=excluded.publish_attempts,
                    last_publish_error=excluded.last_publish_error,
                    publish_response_json=excluded.publish_response_json,
                    latest_views=excluded.latest_views,
                    latest_likes=excluded.latest_likes,
                    latest_engagement_score=excluded.latest_engagement_score,
                    metrics_updated_at=excluded.metrics_updated_at,
                    updated_at=excluded.updated_at,
                    reviewed_at=excluded.reviewed_at
                """,
                (
                    job.id,
                    job.slug,
                    job.topic,
                    job.candidate_id,
                    job.source_name,
                    job.source_url,
                    job.status.value if isinstance(job.status, JobStatus) else str(job.status),
                    job.score,
                    job.quality_score,
                    1 if job.quality_passed else 0,
                    job.content_format,
                    job.hook_strategy,
                    job.target_audience,
                    job.strategy_json,
                    job.script_json,
                    job.youtube_title,
                    job.youtube_description,
                    job.youtube_tags,
                    job.instagram_caption,
                    job.video_path,
                    job.thumbnail_path,
                    job.audio_path,
                    job.notes,
                    job.publish_status.value if isinstance(job.publish_status, PublishStatus) else str(job.publish_status),
                    job.published_platform,
                    job.platform_post_id,
                    job.platform_url,
                    job.published_at,
                    job.publish_attempts,
                    job.last_publish_error,
                    job.publish_response_json,
                    job.latest_views,
                    job.latest_likes,
                    job.latest_engagement_score,
                    job.metrics_updated_at,
                    job.created_at,
                    job.updated_at,
                    job.reviewed_at,
                ),
            )
            conn.commit()
        return job

    def get_job(self, job_id: str) -> JobRecord | None:
        """Fetch a job by ID or slug."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM jobs WHERE id = ? OR slug = ?", (job_id, job_id))
            row = cursor.fetchone()
            return self._row_to_job(row) if row else None

    def list_jobs(self, status: str | JobStatus | None = None, limit: int = 50) -> list[JobRecord]:
        """List jobs ordered by newest first, optionally filtered by status."""
        query = "SELECT * FROM jobs"
        params: list[Any] = []
        if status:
            val = status.value if isinstance(status, JobStatus) else str(status)
            query += " WHERE status = ?"
            params.append(val)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_job(r) for r in cursor.fetchall()]

    def update_status(self, job_id: str, status: JobStatus | str, notes: str | None = None) -> JobRecord | None:
        """Update job approval status and timestamp."""
        job = self.get_job(job_id)
        if not job:
            return None

        status_val = status.value if isinstance(status, JobStatus) else str(status)
        now = datetime.now(timezone.utc).isoformat()
        job.status = JobStatus(status_val)
        job.updated_at = now
        job.reviewed_at = now
        if notes is not None:
            job.notes = notes

        return self.save_job(job)

    def update_metadata(
        self,
        job_id: str,
        *,
        youtube_title: str | None = None,
        youtube_description: str | None = None,
        youtube_tags: str | None = None,
        instagram_caption: str | None = None,
        notes: str | None = None,
    ) -> JobRecord | None:
        """Update editable platform metadata for a job."""
        job = self.get_job(job_id)
        if not job:
            return None

        if youtube_title is not None:
            job.youtube_title = youtube_title
        if youtube_description is not None:
            job.youtube_description = youtube_description
        if youtube_tags is not None:
            job.youtube_tags = youtube_tags
        if instagram_caption is not None:
            job.instagram_caption = instagram_caption
        if notes is not None:
            job.notes = notes

        return self.save_job(job)

    def update_job_metrics(
        self,
        job_id: str,
        *,
        views: int,
        likes: int,
        engagement_score: float,
    ) -> JobRecord | None:
        """Update aggregated summary metrics for a job."""
        job = self.get_job(job_id)
        if not job:
            return None

        job.latest_views = views
        job.latest_likes = likes
        job.latest_engagement_score = engagement_score
        job.metrics_updated_at = datetime.now(timezone.utc).isoformat()
        return self.save_job(job)

    # -- Performance Snapshots (Phase 9) -----------------------------------

    def save_snapshot(self, snapshot: PerformanceSnapshot) -> PerformanceSnapshot:
        """Insert or replace a performance metrics snapshot."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO performance_snapshots (
                    id, job_id, slug, platform, post_id,
                    views, likes, comments, shares,
                    watch_time_seconds, avg_view_duration_seconds,
                    retention_rate_pct, impressions, ctr_pct,
                    engagement_score, snapshot_at, raw_response_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.id,
                    snapshot.job_id,
                    snapshot.slug,
                    snapshot.platform,
                    snapshot.post_id,
                    snapshot.metrics.views,
                    snapshot.metrics.likes,
                    snapshot.metrics.comments,
                    snapshot.metrics.shares,
                    snapshot.metrics.watch_time_seconds,
                    snapshot.metrics.avg_view_duration_seconds,
                    snapshot.metrics.retention_rate_pct,
                    snapshot.metrics.impressions,
                    snapshot.metrics.ctr_pct,
                    snapshot.engagement_score or snapshot.metrics.engagement_score,
                    snapshot.snapshot_at,
                    json.dumps(snapshot.raw_response, ensure_ascii=False),
                ),
            )
            conn.commit()

        # Update JobRecord latest metrics
        self.update_job_metrics(
            snapshot.job_id,
            views=snapshot.metrics.views,
            likes=snapshot.metrics.likes,
            engagement_score=snapshot.engagement_score or snapshot.metrics.engagement_score,
        )
        return snapshot

    def list_snapshots(
        self,
        job_id: str | None = None,
        slug: str | None = None,
        platform: str | None = None,
        limit: int = 100,
    ) -> list[PerformanceSnapshot]:
        """Fetch historical snapshots ordered by newest first."""
        query = "SELECT * FROM performance_snapshots WHERE 1=1"
        params: list[Any] = []
        if job_id:
            query += " AND (job_id = ? OR slug = ?)"
            params.extend([job_id, job_id])
        elif slug:
            query += " AND slug = ?"
            params.append(slug)
        if platform and platform != "all":
            query += " AND platform = ?"
            params.append(platform)
        query += " ORDER BY snapshot_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_snapshot(r) for r in cursor.fetchall()]

    def get_latest_snapshot(self, job_id: str, platform: str | None = None) -> PerformanceSnapshot | None:
        """Fetch the most recent snapshot for a given job and platform."""
        snapshots = self.list_snapshots(job_id=job_id, platform=platform, limit=1)
        return snapshots[0] if snapshots else None

    # -- Row Converters ----------------------------------------------------

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> JobRecord:
        d = dict(row)
        return JobRecord(
            id=d["id"],
            slug=d["slug"],
            topic=d["topic"],
            candidate_id=d.get("candidate_id"),
            source_name=d.get("source_name"),
            source_url=d.get("source_url"),
            status=JobStatus(d["status"]) if d.get("status") in [s.value for s in JobStatus] else JobStatus.PENDING_REVIEW,
            score=float(d.get("score") or 0.0),
            quality_score=float(d.get("quality_score") or 0.0),
            quality_passed=bool(d.get("quality_passed", 1)),
            content_format=d.get("content_format") or "explainer",
            hook_strategy=d.get("hook_strategy") or "curiosity_gap",
            target_audience=d.get("target_audience") or "general_consumers",
            strategy_json=d.get("strategy_json") or "{}",
            script_json=d.get("script_json") or "{}",
            youtube_title=d.get("youtube_title") or "",
            youtube_description=d.get("youtube_description") or "",
            youtube_tags=d.get("youtube_tags") or "[]",
            instagram_caption=d.get("instagram_caption") or "",
            video_path=d.get("video_path"),
            thumbnail_path=d.get("thumbnail_path"),
            audio_path=d.get("audio_path"),
            notes=d.get("notes"),
            publish_status=PublishStatus(d["publish_status"]) if d.get("publish_status") in [p.value for p in PublishStatus] else PublishStatus.NOT_STARTED,
            published_platform=d.get("published_platform"),
            platform_post_id=d.get("platform_post_id"),
            platform_url=d.get("platform_url"),
            published_at=d.get("published_at"),
            publish_attempts=int(d.get("publish_attempts") or 0),
            last_publish_error=d.get("last_publish_error"),
            publish_response_json=d.get("publish_response_json") or "{}",
            latest_views=int(d.get("latest_views") or 0),
            latest_likes=int(d.get("latest_likes") or 0),
            latest_engagement_score=float(d.get("latest_engagement_score") or 0.0),
            metrics_updated_at=d.get("metrics_updated_at"),
            created_at=d["created_at"],
            updated_at=d["updated_at"],
            reviewed_at=d.get("reviewed_at"),
        )

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> PerformanceSnapshot:
        d = dict(row)
        raw_json = d.get("raw_response_json") or "{}"
        try:
            raw_dict = json.loads(raw_json)
        except Exception:
            raw_dict = {}

        metrics = PlatformMetrics(
            views=int(d.get("views") or 0),
            likes=int(d.get("likes") or 0),
            comments=int(d.get("comments") or 0),
            shares=int(d.get("shares") or 0),
            watch_time_seconds=float(d.get("watch_time_seconds") or 0.0),
            avg_view_duration_seconds=float(d.get("avg_view_duration_seconds") or 0.0),
            retention_rate_pct=float(d.get("retention_rate_pct") or 0.0),
            impressions=int(d.get("impressions") or 0),
            ctr_pct=float(d.get("ctr_pct") or 0.0),
            updated_at=d["snapshot_at"],
        )

        return PerformanceSnapshot(
            id=d["id"],
            job_id=d["job_id"],
            slug=d["slug"],
            platform=d["platform"],
            post_id=d.get("post_id"),
            metrics=metrics,
            engagement_score=float(d.get("engagement_score") or 0.0),
            snapshot_at=d["snapshot_at"],
            raw_response=raw_dict,
        )

    # -- Operational Audit Logging (Phase 10) ------------------------------

    def save_audit_log(self, record: AuditLogRecord) -> AuditLogRecord:
        """Insert an operational audit log record for a cycle."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO audit_logs (
                    id, cycle_type, started_at, completed_at, duration_seconds,
                    items_collected, candidates_processed, jobs_generated,
                    qa_passed_count, qa_failed_count, published_count, errors_count,
                    status, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.cycle_type,
                    record.started_at,
                    record.completed_at,
                    record.duration_seconds,
                    record.items_collected,
                    record.candidates_processed,
                    record.jobs_generated,
                    record.qa_passed_count,
                    record.qa_failed_count,
                    record.published_count,
                    record.errors_count,
                    record.status,
                    record.details_json,
                ),
            )
            conn.commit()
        return record

    def list_audit_logs(self, limit: int = 50) -> list[AuditLogRecord]:
        """Fetch audit log records ordered by newest first."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM audit_logs ORDER BY started_at DESC LIMIT ?", (limit,))
            return [self._row_to_audit_log(r) for r in cursor.fetchall()]

    def get_published_count_today(self, platform: str | None = None) -> int:
        """Get the number of jobs successfully published today (UTC) to enforce daily rate limits."""
        today_prefix = datetime.now(timezone.utc).date().isoformat()
        query = "SELECT COUNT(*) as count FROM jobs WHERE publish_status = 'published' AND published_at LIKE ?"
        params: list[Any] = [f"{today_prefix}%"]
        if platform and platform != "all":
            query += " AND published_platform = ?"
            params.append(platform)

        with self._get_connection() as conn:
            row = conn.execute(query, params).fetchone()
            return int(row["count"]) if row else 0

    @staticmethod
    def _row_to_audit_log(row: sqlite3.Row) -> AuditLogRecord:
        d = dict(row)
        return AuditLogRecord(
            id=d["id"],
            cycle_type=d.get("cycle_type") or "scheduled_cycle",
            started_at=d["started_at"],
            completed_at=d["completed_at"],
            duration_seconds=float(d.get("duration_seconds") or 0.0),
            items_collected=int(d.get("items_collected") or 0),
            candidates_processed=int(d.get("candidates_processed") or 0),
            jobs_generated=int(d.get("jobs_generated") or 0),
            qa_passed_count=int(d.get("qa_passed_count") or 0),
            qa_failed_count=int(d.get("qa_failed_count") or 0),
            published_count=int(d.get("published_count") or 0),
            errors_count=int(d.get("errors_count") or 0),
            status=d.get("status") or "success",
            details_json=d.get("details_json") or "{}",
        )

    # -------------------------------------------------------------------------
    # Phase A: B2B Business Discovery, Research, Opportunities, Demos & Outreach
    # -------------------------------------------------------------------------

    def save_business(self, business: BusinessRecord) -> BusinessRecord:
        """Insert or update a business record."""
        now = datetime.now(timezone.utc).isoformat()
        business.updated_at = now
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO businesses (
                    id, name, category, city, state, country, address, website,
                    domain, phone, email, source_provider, source_id, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    category=excluded.category,
                    city=excluded.city,
                    state=excluded.state,
                    country=excluded.country,
                    address=excluded.address,
                    website=excluded.website,
                    domain=excluded.domain,
                    phone=excluded.phone,
                    email=excluded.email,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (
                    business.id,
                    business.name,
                    business.category,
                    business.city,
                    business.state,
                    business.country,
                    business.address,
                    business.website,
                    business.domain,
                    business.phone,
                    business.email,
                    business.source_provider,
                    business.source_id,
                    business.status.value if isinstance(business.status, BusinessStatus) else business.status,
                    business.created_at,
                    business.updated_at,
                ),
            )
            conn.commit()
        return business

    def get_business(self, business_id: str) -> Optional[BusinessRecord]:
        """Fetch a business record by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
            return self._row_to_business(row) if row else None

    def get_business_by_domain(self, domain: str) -> Optional[BusinessRecord]:
        """Fetch a business record by its normalized domain."""
        if not domain:
            return None
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM businesses WHERE domain = ?", (domain.strip().lower(),)).fetchone()
            return self._row_to_business(row) if row else None

    def list_businesses(
        self,
        *,
        status: Optional[str] = None,
        category: Optional[str] = None,
        city: Optional[str] = None,
        location: Optional[str] = None,
        no_website_only: bool = False,
        limit: int = 100,
    ) -> List[BusinessRecord]:
        """List businesses matching optional status, category, city, location, or no_website_only filters."""
        query = "SELECT * FROM businesses WHERE 1=1"
        params: List[Any] = []
        if status and status != "all":
            query += " AND status = ?"
            params.append(status)
        if category and category != "all":
            query += " AND category = ?"
            params.append(category)
        if location and location != "all":
            loc_term = f"%{location.strip().lower()}%"
            query += " AND (LOWER(city) LIKE ? OR LOWER(address) LIKE ? OR LOWER(state) LIKE ?)"
            params.extend([loc_term, loc_term, loc_term])
        elif city and city != "all":
            query += " AND LOWER(city) = ?"
            params.append(city.strip().lower())
        if no_website_only:
            query += " AND (website IS NULL OR website = '' OR LOWER(website) LIKE '%facebook.com%' OR LOWER(website) LIKE '%instagram.com%' OR LOWER(website) LIKE '%wa.me%')"
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_business(r) for r in cursor.fetchall()]

    def update_business_status(self, business_id: str, status: BusinessStatus | str) -> Optional[BusinessRecord]:
        """Update a business's lifecycle status."""
        status_val = status.value if isinstance(status, BusinessStatus) else status
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE businesses SET status = ?, updated_at = ? WHERE id = ?",
                (status_val, now, business_id),
            )
            conn.commit()
        return self.get_business(business_id)

    def save_research_evidence(self, evidence: ResearchEvidence) -> ResearchEvidence:
        """Insert or replace a research evidence record."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO research_evidence (
                    id, business_id, category, claim, claim_type, evidence_url,
                    raw_snippet, source_type, confidence, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.id,
                    evidence.business_id,
                    evidence.category.value if isinstance(evidence.category, EvidenceCategory) else evidence.category,
                    evidence.claim,
                    evidence.claim_type.value if isinstance(evidence.claim_type, ClaimType) else evidence.claim_type,
                    evidence.evidence_url,
                    evidence.raw_snippet,
                    evidence.source_type.value if isinstance(evidence.source_type, SourceType) else evidence.source_type,
                    evidence.confidence,
                    evidence.collected_at,
                ),
            )
            conn.commit()
        return evidence

    def list_research_evidence(
        self,
        business_id: str,
        category: Optional[str] = None,
    ) -> List[ResearchEvidence]:
        """List all research evidence claims for a business."""
        query = "SELECT * FROM research_evidence WHERE business_id = ?"
        params: List[Any] = [business_id]
        if category and category != "all":
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY collected_at ASC"

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_evidence(r) for r in cursor.fetchall()]

    def save_business_research(self, research: BusinessResearch) -> BusinessResearch:
        """Insert or replace complete structured research for a business."""
        # Also persist child evidence records
        for ev in research.evidence:
            self.save_research_evidence(ev)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO business_research (
                    business_id, website_exists, website_url, is_mobile_friendly,
                    speed_score, tech_stack_json, services_json, pricing_info,
                    contact_methods_json, social_links_json, booking_system_found,
                    ordering_system_found, observed_weaknesses_json,
                    observed_strengths_json, researched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    research.business_id,
                    1 if research.website_exists else 0,
                    research.website_url,
                    1 if research.is_mobile_friendly else (0 if research.is_mobile_friendly is False else None),
                    research.speed_score,
                    json.dumps(research.tech_stack),
                    json.dumps(research.services),
                    research.pricing_info,
                    json.dumps(research.contact_methods),
                    json.dumps(research.social_links),
                    1 if research.booking_system_found else 0,
                    1 if research.ordering_system_found else 0,
                    json.dumps(research.observed_weaknesses),
                    json.dumps(research.observed_strengths),
                    research.researched_at,
                ),
            )
            conn.commit()
        return research

    def get_business_research(self, business_id: str) -> Optional[BusinessResearch]:
        """Fetch structured research and all associated evidence for a business."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM business_research WHERE business_id = ?", (business_id,)).fetchone()
            if not row:
                return None
            research = self._row_to_research(row)
            research.evidence = self.list_research_evidence(business_id)
            return research

    def save_opportunity(self, opp: OpportunityRecord) -> OpportunityRecord:
        """Insert or replace an identified opportunity record."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO opportunities (
                    id, business_id, opportunity_type, title, problem_summary,
                    proposed_solution, business_value, score, score_reasons_json,
                    risks_json, confidence, priority, qualification_status,
                    evidence_ids_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    opp.id,
                    opp.business_id,
                    opp.opportunity_type.value if isinstance(opp.opportunity_type, OpportunityType) else opp.opportunity_type,
                    opp.title,
                    opp.problem_summary,
                    opp.proposed_solution,
                    opp.business_value,
                    opp.score,
                    json.dumps(opp.score_reasons),
                    json.dumps(opp.risks),
                    opp.confidence,
                    opp.priority.value if isinstance(opp.priority, OpportunityPriority) else opp.priority,
                    opp.qualification_status.value if isinstance(opp.qualification_status, QualificationStatus) else opp.qualification_status,
                    json.dumps(opp.evidence_ids),
                    opp.status,
                    opp.created_at,
                ),
            )
            conn.commit()
        return opp

    def get_opportunity(self, opp_id: str) -> Optional[OpportunityRecord]:
        """Fetch an opportunity record by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opp_id,)).fetchone()
            return self._row_to_opportunity(row) if row else None

    def list_opportunities(
        self,
        *,
        business_id: Optional[str] = None,
        min_score: Optional[float] = None,
        limit: int = 100,
    ) -> List[OpportunityRecord]:
        """List opportunities matching optional filters."""
        query = "SELECT * FROM opportunities WHERE 1=1"
        params: List[Any] = []
        if business_id:
            query += " AND business_id = ?"
            params.append(business_id)
        if min_score is not None:
            query += " AND score >= ?"
            params.append(min_score)
        query += " ORDER BY score DESC, created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_opportunity(r) for r in cursor.fetchall()]

    def save_demo(self, demo: DemoRecord) -> DemoRecord:
        """Insert or replace an interactive prototype demo record."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO demos (
                    id, opportunity_id, business_id, vertical, demo_type,
                    title, artifact_path, preview_url, status, metadata_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    demo.id,
                    demo.opportunity_id,
                    demo.business_id,
                    demo.vertical.value if isinstance(demo.vertical, VerticalType) else demo.vertical,
                    demo.demo_type.value if isinstance(demo.demo_type, DemoType) else demo.demo_type,
                    demo.title,
                    demo.artifact_path,
                    demo.preview_url,
                    demo.status.value if isinstance(demo.status, DemoStatus) else demo.status,
                    json.dumps(demo.metadata_json),
                    demo.created_at,
                ),
            )
            conn.commit()
        return demo

    def get_demo(self, demo_id: str) -> Optional[DemoRecord]:
        """Fetch a demo record by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM demos WHERE id = ?", (demo_id,)).fetchone()
            return self._row_to_demo(row) if row else None

    def list_demos(
        self,
        *,
        business_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[DemoRecord]:
        """List demo records matching optional filters."""
        query = "SELECT * FROM demos WHERE 1=1"
        params: List[Any] = []
        if business_id:
            query += " AND business_id = ?"
            params.append(business_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_demo(r) for r in cursor.fetchall()]

    def save_outreach(self, outreach: OutreachRecord) -> OutreachRecord:
        """Insert or replace a personalized outreach record."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO outreach (
                    id, business_id, opportunity_id, demo_id, recipient_email,
                    recipient_name, subject, body_text, body_html, followup_body,
                    personalization_reasons_json, evidence_used_json,
                    approval_status, send_status, sent_at, provider_message_id,
                    last_error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outreach.id,
                    outreach.business_id,
                    outreach.opportunity_id,
                    outreach.demo_id,
                    outreach.recipient_email,
                    outreach.recipient_name,
                    outreach.subject,
                    outreach.body_text,
                    outreach.body_html,
                    outreach.followup_body,
                    json.dumps(outreach.personalization_reasons),
                    json.dumps(outreach.evidence_used),
                    outreach.approval_status.value if isinstance(outreach.approval_status, ApprovalStatus) else outreach.approval_status,
                    outreach.send_status.value if isinstance(outreach.send_status, SendStatus) else outreach.send_status,
                    outreach.sent_at,
                    outreach.provider_message_id,
                    outreach.last_error,
                    outreach.created_at,
                ),
            )
            conn.commit()
        return outreach

    def get_outreach(self, outreach_id: str) -> Optional[OutreachRecord]:
        """Fetch an outreach record by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM outreach WHERE id = ?", (outreach_id,)).fetchone()
            return self._row_to_outreach(row) if row else None

    def list_outreach(
        self,
        *,
        business_id: Optional[str] = None,
        approval_status: Optional[str] = None,
        send_status: Optional[str] = None,
        limit: int = 100,
    ) -> List[OutreachRecord]:
        """List outreach records matching optional filters."""
        query = "SELECT * FROM outreach WHERE 1=1"
        params: List[Any] = []
        if business_id:
            query += " AND business_id = ?"
            params.append(business_id)
        if approval_status and approval_status != "all":
            query += " AND approval_status = ?"
            params.append(approval_status)
        if send_status and send_status != "all":
            query += " AND send_status = ?"
            params.append(send_status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_outreach(r) for r in cursor.fetchall()]

    def update_outreach_approval(
        self,
        outreach_id: str,
        status: ApprovalStatus | str,
    ) -> Optional[OutreachRecord]:
        """Update outreach human approval status."""
        status_val = status.value if isinstance(status, ApprovalStatus) else status
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE outreach SET approval_status = ? WHERE id = ?",
                (status_val, outreach_id),
            )
            conn.commit()
        return self.get_outreach(outreach_id)

    def update_outreach_send_status(
        self,
        outreach_id: str,
        send_status: SendStatus | str,
        *,
        sent_at: Optional[str] = None,
        provider_message_id: Optional[str] = None,
        last_error: Optional[str] = None,
    ) -> Optional[OutreachRecord]:
        """Update outreach send status after sending attempt."""
        status_val = send_status.value if isinstance(send_status, SendStatus) else send_status
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE outreach
                SET send_status = ?, sent_at = COALESCE(?, sent_at),
                    provider_message_id = COALESCE(?, provider_message_id),
                    last_error = ?
                WHERE id = ?
                """,
                (status_val, sent_at, provider_message_id, last_error, outreach_id),
            )
            conn.commit()
        return self.get_outreach(outreach_id)

    def save_outreach_response(self, resp: OutreachResponse) -> OutreachResponse:
        """Insert or replace an inbound outreach response record."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO outreach_responses (
                    id, outreach_id, business_id, received_at, classification,
                    raw_content, suggested_reply, reply_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resp.id,
                    resp.outreach_id,
                    resp.business_id,
                    resp.received_at,
                    resp.classification.value if isinstance(resp.classification, ResponseClassification) else resp.classification,
                    resp.raw_content,
                    resp.suggested_reply,
                    resp.reply_status.value if isinstance(resp.reply_status, ReplyStatus) else resp.reply_status,
                ),
            )
            conn.commit()
        return resp

    def list_outreach_responses(
        self,
        *,
        outreach_id: Optional[str] = None,
        business_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[OutreachResponse]:
        """List inbound response records."""
        query = "SELECT * FROM outreach_responses WHERE 1=1"
        params: List[Any] = []
        if outreach_id:
            query += " AND outreach_id = ?"
            params.append(outreach_id)
        if business_id:
            query += " AND business_id = ?"
            params.append(business_id)
        query += " ORDER BY received_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_response(r) for r in cursor.fetchall()]

    def save_followup(self, followup: FollowUpRecord) -> FollowUpRecord:
        """Insert or replace a multi-step follow-up record."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO followups (
                    id, outreach_id, business_id, step_number, scheduled_date,
                    subject, body_text, body_html, status, sent_at,
                    provider_message_id, last_error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    followup.id,
                    followup.outreach_id,
                    followup.business_id,
                    followup.step_number,
                    followup.scheduled_date,
                    followup.subject,
                    followup.body_text,
                    followup.body_html,
                    followup.status.value if isinstance(followup.status, FollowUpStatus) else followup.status,
                    followup.sent_at,
                    followup.provider_message_id,
                    followup.last_error,
                    followup.created_at,
                ),
            )
            conn.commit()
        return followup

    def get_followup(self, followup_id: str) -> Optional[FollowUpRecord]:
        """Fetch a follow-up record by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM followups WHERE id = ?", (followup_id,)).fetchone()
            return self._row_to_followup(row) if row else None

    def list_followups(
        self,
        *,
        outreach_id: Optional[str] = None,
        business_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[FollowUpRecord]:
        """List follow-up records matching optional filters."""
        query = "SELECT * FROM followups WHERE 1=1"
        params: List[Any] = []
        if outreach_id:
            query += " AND outreach_id = ?"
            params.append(outreach_id)
        if business_id:
            query += " AND business_id = ?"
            params.append(business_id)
        if status and status != "all":
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY step_number ASC, created_at ASC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [self._row_to_followup(r) for r in cursor.fetchall()]

    def update_followup_status(
        self,
        followup_id: str,
        status: FollowUpStatus | str,
        *,
        sent_at: Optional[str] = None,
        provider_message_id: Optional[str] = None,
        last_error: Optional[str] = None,
    ) -> Optional[FollowUpRecord]:
        """Update follow-up status and dispatch details."""
        status_val = status.value if isinstance(status, FollowUpStatus) else status
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE followups
                SET status = ?, sent_at = COALESCE(?, sent_at),
                    provider_message_id = COALESCE(?, provider_message_id),
                    last_error = ?
                WHERE id = ?
                """,
                (status_val, sent_at, provider_message_id, last_error, followup_id),
            )
            conn.commit()
        return self.get_followup(followup_id)

    # --- Row Deserializers ---

    @staticmethod
    def _row_to_business(row: sqlite3.Row) -> BusinessRecord:
        d = dict(row)
        return BusinessRecord(
            id=d["id"],
            name=d["name"],
            category=d["category"],
            city=d["city"],
            state=d.get("state"),
            country=d.get("country") or "India",
            address=d.get("address"),
            website=d.get("website"),
            domain=d.get("domain"),
            phone=d.get("phone"),
            email=d.get("email"),
            source_provider=d.get("source_provider") or "manual_input",
            source_id=d.get("source_id"),
            status=BusinessStatus(d.get("status") or "discovered"),
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )

    @staticmethod
    def _row_to_evidence(row: sqlite3.Row) -> ResearchEvidence:
        d = dict(row)
        return ResearchEvidence(
            id=d["id"],
            business_id=d["business_id"],
            category=EvidenceCategory(d["category"]),
            claim=d["claim"],
            claim_type=ClaimType(d.get("claim_type") or "verified_fact"),
            evidence_url=d.get("evidence_url"),
            raw_snippet=d.get("raw_snippet"),
            source_type=SourceType(d.get("source_type") or "website_homepage"),
            confidence=float(d.get("confidence") or 1.0),
            collected_at=d["collected_at"],
        )

    @staticmethod
    def _row_to_research(row: sqlite3.Row) -> BusinessResearch:
        d = dict(row)
        return BusinessResearch(
            business_id=d["business_id"],
            website_exists=bool(d.get("website_exists")),
            website_url=d.get("website_url"),
            is_mobile_friendly=bool(d["is_mobile_friendly"]) if d.get("is_mobile_friendly") is not None else None,
            speed_score=float(d["speed_score"]) if d.get("speed_score") is not None else None,
            tech_stack=json.loads(d.get("tech_stack_json") or "[]"),
            services=json.loads(d.get("services_json") or "[]"),
            pricing_info=d.get("pricing_info"),
            contact_methods=json.loads(d.get("contact_methods_json") or "[]"),
            social_links=json.loads(d.get("social_links_json") or "{}"),
            booking_system_found=bool(d.get("booking_system_found")),
            ordering_system_found=bool(d.get("ordering_system_found")),
            observed_weaknesses=json.loads(d.get("observed_weaknesses_json") or "[]"),
            observed_strengths=json.loads(d.get("observed_strengths_json") or "[]"),
            researched_at=d["researched_at"],
        )

    @staticmethod
    def _row_to_opportunity(row: sqlite3.Row) -> OpportunityRecord:
        d = dict(row)
        return OpportunityRecord(
            id=d["id"],
            business_id=d["business_id"],
            opportunity_type=OpportunityType(d["opportunity_type"]),
            title=d["title"],
            problem_summary=d["problem_summary"],
            proposed_solution=d["proposed_solution"],
            business_value=d["business_value"],
            score=float(d["score"]),
            score_reasons=json.loads(d.get("score_reasons_json") or "[]"),
            risks=json.loads(d.get("risks_json") or "[]"),
            confidence=float(d.get("confidence") or 1.0),
            priority=OpportunityPriority(d.get("priority") or "medium"),
            qualification_status=QualificationStatus(d.get("qualification_status") or "qualified"),
            evidence_ids=json.loads(d.get("evidence_ids_json") or "[]"),
            status=d.get("status") or "identified",
            created_at=d["created_at"],
        )

    @staticmethod
    def _row_to_demo(row: sqlite3.Row) -> DemoRecord:
        d = dict(row)
        return DemoRecord(
            id=d["id"],
            opportunity_id=d["opportunity_id"],
            business_id=d["business_id"],
            vertical=VerticalType(d.get("vertical") or "general_smb"),
            demo_type=DemoType(d.get("demo_type") or "landing_page"),
            title=d["title"],
            artifact_path=d["artifact_path"],
            preview_url=d.get("preview_url"),
            status=DemoStatus(d.get("status") or "ready"),
            metadata_json=json.loads(d.get("metadata_json") or "{}"),
            created_at=d["created_at"],
        )

    @staticmethod
    def _row_to_outreach(row: sqlite3.Row) -> OutreachRecord:
        d = dict(row)
        return OutreachRecord(
            id=d["id"],
            business_id=d["business_id"],
            opportunity_id=d["opportunity_id"],
            demo_id=d.get("demo_id"),
            recipient_email=d["recipient_email"],
            recipient_name=d.get("recipient_name"),
            subject=d["subject"],
            body_text=d["body_text"],
            body_html=d.get("body_html"),
            followup_body=d.get("followup_body"),
            personalization_reasons=json.loads(d.get("personalization_reasons_json") or "[]"),
            evidence_used=json.loads(d.get("evidence_used_json") or "[]"),
            approval_status=ApprovalStatus(d.get("approval_status") or "pending_review"),
            send_status=SendStatus(d.get("send_status") or "draft"),
            sent_at=d.get("sent_at"),
            provider_message_id=d.get("provider_message_id"),
            last_error=d.get("last_error"),
            created_at=d["created_at"],
        )

    @staticmethod
    def _row_to_response(row: sqlite3.Row) -> OutreachResponse:
        d = dict(row)
        return OutreachResponse(
            id=d["id"],
            outreach_id=d["outreach_id"],
            business_id=d["business_id"],
            received_at=d["received_at"],
            classification=ResponseClassification(d.get("classification") or "unclear"),
            raw_content=d["raw_content"],
            suggested_reply=d.get("suggested_reply"),
            reply_status=ReplyStatus(d.get("reply_status") or "pending_review"),
        )

    @staticmethod
    def _row_to_followup(row: sqlite3.Row) -> FollowUpRecord:
        d = dict(row)
        return FollowUpRecord(
            id=d["id"],
            outreach_id=d["outreach_id"],
            business_id=d["business_id"],
            step_number=int(d.get("step_number") or 1),
            scheduled_date=d.get("scheduled_date"),
            subject=d["subject"],
            body_text=d["body_text"],
            body_html=d.get("body_html"),
            status=FollowUpStatus(d.get("status") or "pending_review"),
            sent_at=d.get("sent_at"),
            provider_message_id=d.get("provider_message_id"),
            last_error=d.get("last_error"),
            created_at=d["created_at"],
        )