"""!Unit tests for project queue listing endpoint."""

from fastapi import HTTPException

from apps.api.main import JOBS, PROJECTS, list_project_queue


def _seed_queue_jobs() -> None:
    PROJECTS.clear()
    JOBS.clear()
    PROJECTS["p1"] = {"project_id": "p1", "name": "P1"}
    JOBS["j1"] = {
        "job_id": "j1",
        "status": "queued",
        "submitted_at": "2020-01-01T00:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }
    JOBS["j2"] = {
        "job_id": "j2",
        "status": "running",
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "started_at": "2026-03-30T00:01:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s2"},
        "events": [],
    }
    JOBS["j3"] = {
        "job_id": "j3",
        "status": "completed",
        "submitted_at": "2026-03-30T00:02:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s3"},
        "events": [],
    }


def test_queue_listing_includes_queued_and_running() -> None:
    """!Queue listing should include queued and optional running jobs."""
    _seed_queue_jobs()
    result = list_project_queue("p1", include_running=True, stale_after_seconds=60, limit=10, offset=0)
    assert result["count"] == 2
    assert result["returned"] == 2
    assert result["jobs"][0]["job_id"] == "j1"
    assert result["jobs"][0]["is_stale"] is True


def test_queue_listing_can_exclude_running() -> None:
    """!Running jobs should be omitted when include_running is false."""
    _seed_queue_jobs()
    result = list_project_queue("p1", include_running=False, stale_after_seconds=60, limit=10, offset=0)
    assert result["count"] == 1
    assert result["jobs"][0]["status"] == "queued"


def test_queue_listing_validates_input() -> None:
    """!Invalid paging and stale threshold params should fail."""
    _seed_queue_jobs()
    try:
        list_project_queue("p1", limit=0)
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected HTTPException for limit")

    try:
        list_project_queue("p1", stale_after_seconds=0)
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected HTTPException for stale_after_seconds")
