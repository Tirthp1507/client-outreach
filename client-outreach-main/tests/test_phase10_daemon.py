"""Tests for AutomationDaemon single cycle and error isolation."""

from db.database import Database
from scheduler.daemon import AutomationDaemon


def test_daemon_execute_single_cycle(tmp_path):
    db = Database(tmp_path / "test.db")
    daemon = AutomationDaemon(
        db=db,
        interval_minutes=10,
        batch_limit=1,
        dry_run=True,
    )

    record = daemon.execute_single_cycle(cycle_type="test_cycle")
    assert record.id.startswith("audit_test_cycle_")
    assert record.status in ("success", "partial")
    assert record.duration_seconds >= 0

    # Ensure saved to SQLite
    audits = db.list_audit_logs(limit=10)
    assert len(audits) == 1
    assert audits[0].id == record.id