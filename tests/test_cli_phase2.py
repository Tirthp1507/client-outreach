"""CLI tests for Phase 2 collect and process commands."""

import json
from pathlib import Path
from cli import build_parser, main
from collectors.models import CollectionBatch, RawContentItem


def test_cli_parser_has_all_commands():
    parser = build_parser()
    # Check that generate, doctor, collect, process are registered
    subparsers = [action for action in parser._actions if action.dest == "command"][0]
    assert "generate" in subparsers.choices
    assert "doctor" in subparsers.choices
    assert "collect" in subparsers.choices
    assert "process" in subparsers.choices


def test_cli_process_command_with_mock_collected_file(tmp_path, monkeypatch):
    collected_dir = tmp_path / "collected"
    collected_dir.mkdir(parents=True)
    latest_json = collected_dir / "latest.json"

    batch = CollectionBatch(
        total_items=2,
        items=[
            RawContentItem(
                id="1",
                source_name="TestFeed",
                title="Top 3 AI Automation Hacks",
                url="https://example.com/1",
                content="Here are three practical automation hacks for content creators.",
            ),
            RawContentItem(
                id="2",
                source_name="TestFeed",
                title="Top 3 AI Automation Hacks",
                url="https://example.com/1",  # duplicate URL
                content="Duplicate entry",
            ),
        ],
    )
    latest_json.write_text(batch.model_dump_json(), encoding="utf-8")

    out_proc = tmp_path / "processed"
    exit_code = main(["process", "--input", str(latest_json), "--output-dir", str(tmp_path), "--limit", "5"])
    assert exit_code == 0
    assert (out_proc / "latest.json").exists()