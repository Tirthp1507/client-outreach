"""Operational safeguards, daily rate limiting, storage retention pruning, and health monitoring."""

from __future__ import annotations

import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT, get_config
from db.database import Database
from video import has_ffmpeg
from voice import EdgeTTSEngine

logger = logging.getLogger(__name__)



class PublishQuotaGuard:
    """Enforces daily publishing quotas to protect accounts against spam flags and rate limits."""

    def __init__(self, db: Database | None = None, config: dict[str, Any] | None = None) -> None:
        self.db = db or Database()
        self.config = config or get_config()

    def get_daily_limit(self, platform: str) -> int:
        pub_cfg = self.config.get("publishing", {})
        safeguards_cfg = pub_cfg.get("safeguards", {})
        daily_limits = safeguards_cfg.get("daily_limits", {"youtube": 5, "instagram": 5})
        return int(daily_limits.get(platform, 5))

    def can_publish(self, platform: str) -> tuple[bool, str]:
        """Check if target platform is within daily publishing quota."""
        limit = self.get_daily_limit(platform)
        published_today = self.db.get_published_count_today(platform=platform)

        if published_today >= limit:
            msg = f"Daily publish quota exceeded for {platform} ({published_today}/{limit} posts published today UTC)"
            logger.warning(msg)
            return False, msg

        return True, f"Within daily quota ({published_today}/{limit} posts published today UTC)"

    def get_quota_status(self) -> dict[str, dict[str, Any]]:
        """Return current quota usage for all supported platforms."""
        status = {}
        for p in ["youtube", "instagram"]:
            limit = self.get_daily_limit(p)
            used = self.db.get_published_count_today(platform=p)
            status[p] = {
                "limit": limit,
                "used_today": used,
                "remaining": max(0, limit - used),
                "allowed": used < limit,
            }
        return status


class StoragePruningEngine:
    """Safely cleans up stale intermediate drafts, audio, and old collection batches."""

    def __init__(self, output_dir: Path | str | None = None) -> None:
        if output_dir is None:
            self.output_dir = PROJECT_ROOT / "output"
        else:
            self.output_dir = Path(output_dir)

    def prune_artifacts(
        self,
        *,
        older_than_days: int = 7,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Remove intermediate artifacts older than the specified retention window."""
        cutoff_epoch = time.time() - (older_than_days * 86400)
        target_dirs = ["audio", "drafts", "collected"]

        deleted_files: list[str] = []
        freed_bytes: int = 0

        for d_name in target_dirs:
            target_path = self.output_dir / d_name
            if not target_path.exists():
                continue

            for f in target_path.rglob("*"):
                if f.is_file():
                    try:
                        mtime = f.stat().st_mtime
                        if older_than_days <= 0 or mtime <= cutoff_epoch:
                            size = f.stat().st_size
                            if not dry_run:
                                f.unlink()
                            deleted_files.append(str(f.relative_to(self.output_dir)))
                            freed_bytes += size

                    except Exception as exc:
                        logger.warning("Error pruning file %s: %s", f, exc)

        freed_mb = round(freed_bytes / (1024 * 1024), 2)
        return {
            "older_than_days": older_than_days,
            "dry_run": dry_run,
            "deleted_count": len(deleted_files),
            "freed_mb": freed_mb,
            "deleted_files": deleted_files[:50],
        }


class SystemHealthMonitor:
    """Monitors system resources, database integrity, and operational queue health."""

    def __init__(self, db: Database | None = None, output_dir: Path | str | None = None) -> None:
        self.db = db or Database()
        self.output_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "output"

    def check_health(self) -> dict[str, Any]:
        """Perform comprehensive readiness and storage health checks."""
        # 1. Disk Space
        disk_free_gb = 0.0
        try:
            total, used, free = shutil.disk_usage(str(self.output_dir))
            disk_free_gb = round(free / (1024 ** 3), 2)
        except Exception:
            disk_free_gb = 100.0

        # 2. Database connectivity & job counts
        jobs = self.db.list_jobs(limit=500)
        pending_count = sum(1 for j in jobs if j.status.value == "pending_review")
        staged_count = sum(1 for j in jobs if j.status.value == "staged")
        published_count = sum(1 for j in jobs if j.status.value == "published")
        failed_count = sum(1 for j in jobs if j.status.value == "failed")

        # 3. Core dependencies
        ffmpeg_ok = has_ffmpeg()
        tts_ok = True
        try:
            EdgeTTSEngine()
        except Exception:
            tts_ok = False

        # 4. Quota status
        quota_guard = PublishQuotaGuard(db=self.db)
        quota = quota_guard.get_quota_status()

        # 5. Recent audit log
        recent_audits = self.db.list_audit_logs(limit=5)

        is_healthy = ffmpeg_ok and tts_ok and (disk_free_gb > 1.0)

        return {
            "status": "healthy" if is_healthy else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "disk_free_gb": disk_free_gb,
            "disk_healthy": disk_free_gb > 2.0,
            "ffmpeg_ready": ffmpeg_ok,
            "tts_ready": tts_ok,
            "jobs_summary": {
                "total": len(jobs),
                "pending_review": pending_count,
                "staged": staged_count,
                "published": published_count,
                "failed": failed_count,
            },
            "quota_status": quota,
            "recent_audit_count": len(recent_audits),
            "last_cycle_status": recent_audits[0].status if recent_audits else "no_cycles_yet",
        }