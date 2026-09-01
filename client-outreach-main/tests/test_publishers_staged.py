"""Tests for YouTube and Instagram publisher staged mode and safety guards."""

import json
from pathlib import Path
from db.models import JobRecord, JobStatus
from publishers import InstagramPublisher, YouTubePublisher


def test_youtube_publisher_staged_mode(tmp_path):
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"0" * 1000)

    job = JobRecord(
        id="job_yt_1",
        slug="yt-test",
        topic="YouTube Test",
        status=JobStatus.APPROVED,
        youtube_title="YouTube Test Title",
        youtube_description="Test Description",
        youtube_tags='["test", "tech"]',
        video_path=str(vid_file),
    )

    pub = YouTubePublisher(live=False)
    res = pub.publish(job)

    assert res.status == "staged"
    assert res.platform == "youtube"
    assert res.payload_file is not None
    assert Path(res.payload_file).exists()

    payload = json.loads(Path(res.payload_file).read_text(encoding="utf-8"))
    assert payload["snippet"]["title"] == "YouTube Test Title #Shorts"
    assert payload["snippet"]["tags"] == ["test", "tech"]


def test_instagram_publisher_staged_mode(tmp_path):
    vid_file = tmp_path / "video.mp4"
    vid_file.write_bytes(b"0" * 1000)

    job = JobRecord(
        id="job_ig_1",
        slug="ig-test",
        topic="Instagram Test",
        status=JobStatus.APPROVED,
        instagram_caption="⚡ Instagram Test Caption #shorts",
        video_path=str(vid_file),
    )

    pub = InstagramPublisher(live=False)
    res = pub.publish(job)

    assert res.status == "staged"
    assert res.platform == "instagram"
    assert res.payload_file is not None
    assert Path(res.payload_file).exists()

    payload = json.loads(Path(res.payload_file).read_text(encoding="utf-8"))
    assert payload["media_type"] == "REELS"
    assert payload["caption"] == "⚡ Instagram Test Caption #shorts"