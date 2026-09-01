"""Tests for Phase 10 CLI subcommands: daemon, prune, audit, safeguards."""

from cli import build_parser, cmd_audit, cmd_daemon, cmd_prune, cmd_safeguards
from db.database import Database
from db.models import AuditLogRecord


def test_phase10_cli_parser_registration():
    parser = build_parser()

    dae_args = parser.parse_args(["daemon", "--once", "--interval-minutes", "30"])
    assert dae_args.command == "daemon"
    assert dae_args.once is True
    assert dae_args.interval_minutes == 30

    pru_args = parser.parse_args(["prune", "--days", "3", "--dry-run"])
    assert pru_args.command == "prune"
    assert pru_args.days == 3
    assert pru_args.dry_run is True

    aud_args = parser.parse_args(["audit", "--limit", "10"])
    assert aud_args.command == "audit"
    assert aud_args.limit == 10

    saf_args = parser.parse_args(["safeguards"])
    assert saf_args.command == "safeguards"


def test_phase10_cli_execution(tmp_path):
    parser = build_parser()
    db = Database(tmp_path / "automation.db")

    # 1. Daemon single cycle
    dae_args = parser.parse_args(["daemon", "--once", "--output-dir", str(tmp_path), "--dry-run"])
    rc_dae = cmd_daemon(dae_args)
    assert rc_dae == 0

    # 2. Audit logs view
    aud_args = parser.parse_args(["audit", "--output-dir", str(tmp_path)])
    rc_aud = cmd_audit(aud_args)
    assert rc_aud == 0

    # 3. Safeguards & health view
    saf_args = parser.parse_args(["safeguards", "--output-dir", str(tmp_path)])
    rc_saf = cmd_safeguards(saf_args)
    assert rc_saf == 0

    # 4. Pruning dry-run
    pru_args = parser.parse_args(["prune", "--days", "1", "--dry-run", "--output-dir", str(tmp_path)])
    rc_pru = cmd_prune(pru_args)
    assert rc_pru == 0