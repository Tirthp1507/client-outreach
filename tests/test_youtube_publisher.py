"""Tests for YouTubePublisher validation, staging, and mock upload."""

from unittest.mock import MagicMock, patch
from db.models import JobRecord, JobStatus
from publishers.youtube_publisher import YouTubePublisher


def test_youtube_publisher_validations(tmp_path):
    pub = YouTubePublisher({"publishers": {"youtube": {"privacy_status": "unlisted"}}})

    # Missing video
    bad_job = JobRecord(id="j1", slug="s1", topic="Topic", status=JobStatus.APPROVED, video_path=str(tmp_path / "missing.mp4"))
    res = pub.publish(bad_job, dry_run=True)
    assert res.status == "failed"
    assert "does not exist" in res.error

    # Valid video
    vid_file = tmp_path / "test.mp4"
    vid_file.write_bytes(b"0" * 100_000)
    valid_job = JobRecord(
        id="j2",
        slug="s2",
        topic="Valid YouTube Shorts Topic",
        status=JobStatus.APPROVED,
        youtube_title="Valid YouTube Shorts Topic #Shorts",
        video_path=str(vid_file),
    )

    res_dry = pub.publish(valid_job, dry_run=True)
    assert res_dry.status == "published_dry_run"
    assert "youtube.com/shorts" in res_dry.url
    assert res_dry.payload_file is not None


def test_youtube_publisher_mock_live_upload(tmp_path):
    vid_file = tmp_path / "test.mp4"
    vid_file.write_bytes(b"0" * 100_000)
    job = JobRecord(
        id="j3",
        slug="s3",
        topic="Live Upload Test",
        status=JobStatus.APPROVED,
        youtube_title="Live Upload Test #Shorts",
        video_path=str(vid_file),
    )

    pub = YouTubePublisher(
        {"publishers": {"youtube": {"access_token": "mock_oauth_token"}}},
        live=True,
    )
    assert pub.validate_credentials() is True

    # Mock urllib responses
    mock_resumable_resp = MagicMock()
    mock_resumable_resp.headers = {"Location": "https://upload.youtube.com/test_resumable"}
    mock_resumable_resp.__enter__.return_value = mock_resumable_resp

    mock_upload_resp = MagicMock()
    mock_upload_resp.read.return_value = b'{"id": "mock_yt_vid_999"}'
    mock_upload_resp.__enter__.return_value = mock_upload_resp

    with patch("urllib.request.urlopen", side_effect=[mock_resumable_resp, mock_upload_resp]):
        res = pub.publish(job, dry_run=False)

    assert res.status == "published"
    assert res.post_id == "mock_yt_vid_999"
    assert "https://youtube.com/shorts/mock_yt_vid_999" in res.url