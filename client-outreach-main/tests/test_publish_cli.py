"""Tests for CLI publish and publish-status subcommands."""

from cli import build_parser, main
from db.database import Database
from db.models import JobRecord, JobStatus


def test_cli_publish_parser_registration():
    parser = build_parser()
    args_pub = parser.parse_args(["publish", "--job-id", "job_1", "--platform", "youtube", "--dry-run"])
    assert args_pub.command == "publish"
    assert args_pub.job_id == "job_1"
    assert args_pub.dry_run is True

    args_stat = parser.parse_args(["publish-status", "--job-id", "job_1"])
    assert args_stat.command == "publish-status"
    assert args_stat.job_id == "job_1"


def test_cli_publish_dry_run_approved_job(tmp_path, capsys):
    db_file = tmp_path / "automation.db"
    db = Database(db_file)

    vid_file = tmp_path / "sample.mp4"
    vid_file.write_bytes(b"0" * 100_000)

    job = JobRecord(
        id="job_cli_1",
        slug="cli-sample",
        topic="CLI Sample Topic",
        status=JobStatus.APPROVED,
        youtube_title="CLI Sample Topic #Shorts",
        instagram_caption="CLI Sample Caption",
        video_path=str(vid_file),
    )
    db.save_job(job)

    # Execute publish --job-id job_cli_1 --platform youtube --dry-run
    exit_code = main(["publish", "--job-id", "job_cli_1", "--platform", "youtube", "--dry-run", "--output-dir", str(tmp_path)])
    assert exit_code == 0

    # Execute publish-status --job-id job_cli_1
    status_code = main(["publish-status", "--job-id", "job_cli_1", "--output-dir", str(tmp_path)])
    assert status_code == 0