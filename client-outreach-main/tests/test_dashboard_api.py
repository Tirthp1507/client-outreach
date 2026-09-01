"""Tests for Dashboard HTTP server and REST endpoints."""

import json
import threading
from urllib.request import Request, urlopen

from analytics.models import PerformanceSnapshot, PlatformMetrics
from db.database import Database
from db.models import JobRecord, JobStatus
from dashboard.server import run_dashboard_server


def test_dashboard_api_endpoints(tmp_path):
    db = Database(tmp_path / "dash_test.db")
    job = JobRecord(
        id="job_dash_1",
        slug="dash-test",
        topic="Dashboard Test Video",
        status=JobStatus.PENDING_REVIEW,
        score=75.0,
        quality_score=90.0,
        youtube_title="Original YouTube Title",
        instagram_caption="Original IG Caption",
    )
    db.save_job(job)

    server = run_dashboard_server(host="127.0.0.1", port=8991, db=db)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()

    base_url = "http://127.0.0.1:8991"

    try:
        # 1. GET /
        with urlopen(f"{base_url}/") as res:
            assert res.status == 200
            html = res.read().decode("utf-8")
            assert "AI Content Studio" in html

        # 2. GET /api/jobs
        with urlopen(f"{base_url}/api/jobs") as res:
            assert res.status == 200
            data = json.loads(res.read().decode("utf-8"))
            assert len(data) == 1
            assert data[0]["id"] == "job_dash_1"

        db.save_snapshot(
            PerformanceSnapshot(
                id="snap_dash_i",
                job_id=job.id,
                slug="dash-test",
                platform="youtube",
                metrics=PlatformMetrics(views=1000, likes=100),
                engagement_score=70.0,
            )
        )
        with urlopen(f"{base_url}/api/analytics/insights") as res:
            assert res.status == 200
            insights = json.loads(res.read().decode("utf-8"))
            assert insights["total_snapshots"] == 1
            assert insights["dimensions"]

        # 3. POST /api/jobs/job_dash_1/edit
        req = Request(
            f"{base_url}/api/jobs/job_dash_1/edit",
            data=json.dumps({"youtube_title": "Edited Title #Shorts"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req) as res:
            assert res.status == 200
            updated = json.loads(res.read().decode("utf-8"))
            assert updated["youtube_title"] == "Edited Title #Shorts"

        # 4. POST /api/jobs/job_dash_1/status
        req = Request(
            f"{base_url}/api/jobs/job_dash_1/status",
            data=json.dumps({"status": "approved"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req) as res:
            assert res.status == 200
            updated = json.loads(res.read().decode("utf-8"))
            assert updated["status"] == "approved"

    finally:
        server.shutdown()
        server.server_close()