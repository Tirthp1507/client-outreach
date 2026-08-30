"""Tests for CLI auto command and end-to-end orchestration."""

import json
from pathlib import Path
from cli import build_parser, main
from processors.models import ProcessedCandidate, ProcessingBatch


def test_cli_auto_command_registered():
    parser = build_parser()
    subparsers = [action for action in parser._actions if action.dest == "command"][0]
    assert "auto" in subparsers.choices


def test_cli_auto_with_skip_collect_and_no_video(tmp_path):
    proc_dir = tmp_path / "processed"
    proc_dir.mkdir(parents=True)
    latest_json = proc_dir / "latest.json"

    cand = ProcessedCandidate(
        id="cand_auto_1",
        source_name="TechDaily",
        source_url="https://techdaily.org/article",
        raw_title="How to optimize Python performance",
        clean_title="How to optimize Python performance",
        topic_suggestion="How to Optimize Python Performance",
        summary="Use vectorization, built-in functions, and profile CPU usage.",
        clean_body="Here is a step by step guide to profiling and improving Python speed.",
        score=65.0,
        reasons=["High interest keywords"],
    )
    batch = ProcessingBatch(total_input=1, total_valid=1, candidates=[cand])
    latest_json.write_text(batch.model_dump_json(), encoding="utf-8")

    exit_code = main(["auto", "--output-dir", str(tmp_path), "--skip-collect", "--no-video", "--limit", "1", "--seed", "1"])
    assert exit_code == 0

    # Verify history recorded
    hist_file = tmp_path / "history.json"
    assert hist_file.exists()
    hist_data = json.loads(hist_file.read_text(encoding="utf-8"))
    assert hist_data["total_records"] == 1
    assert hist_data["records"][0]["candidate_id"] == "cand_auto_1"