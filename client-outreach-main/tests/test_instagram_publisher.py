"""Tests for InstagramPublisher validation, staging, and mock Graph API publishing."""

from unittest.mock import MagicMock, patch
from db.models import JobRecord, JobStatus
from publishers.instagram_publisher import InstagramPublisher


def test_instagram_publisher_validations(tmp_path):
    pub = InstagramPublisher({"publishers": {"instagram": {"account_id": "act_1", "access_token": "tok_1"}}})
    assert pub.validate_credentials() is True

    # Missing video
    bad_job = JobRecord(id="j1", slug="s1", topic="Topic", status=JobStatus.APPROVED, video_path=str(tmp_path / "missing.mp4"))
    res = pub.publish(bad_job, dry_run=True)
    assert res.status == "failed"

    # Valid video
    vid_file = tmp_path / "test.mp4"
    vid_file.write_bytes(b"0" * 100_000)
    valid_job = JobRecord(
        id="j2",
        slug="s2",
        topic="Valid Instagram Reel",
        status=JobStatus.APPROVED,
        instagram_caption="Valid Instagram Reel #reels #ai",
        video_path=str(vid_file),
    )

    res_dry = pub.publish(valid_job, dry_run=True)
    assert res_dry.status == "published_dry_run"
    assert "instagram.com/reel" in res_dry.url


def test_instagram_publisher_mock_live_publish(tmp_path):
    vid_file = tmp_path / "test.mp4"
    vid_file.write_bytes(b"0" * 100_000)
    job = JobRecord(
        id="j3",
        slug="s3",
        topic="Live Reel Test",
        status=JobStatus.APPROVED,
        instagram_caption="Live Reel #tech",
        video_path=str(vid_file),
    )

    pub = InstagramPublisher(
        {"publishers": {"instagram": {"account_id": "17841400000000", "access_token": "mock_ig_token"}}},
        live=True,
    )

    # Step 1: container creation resp, Step 2: publish resp
    mock_container_resp = MagicMock()
    mock_container_resp.read.return_value = b'{"id": "container_9999"}'
    mock_container_resp.__enter__.return_value = mock_container_resp

    mock_pub_resp = MagicMock()
    mock_pub_resp.read.return_value = b'{"id": "reel_post_8888"}'
    mock_pub_resp.__enter__.return_value = mock_pub_resp

    with patch("urllib.request.urlopen", side_effect=[mock_container_resp, mock_pub_resp]):
        res = pub.publish(job, dry_run=False)

    assert res.status == "published"
    assert res.post_id == "reel_post_8888"
    assert "https://instagram.com/reel/reel_post_8888" in res.url