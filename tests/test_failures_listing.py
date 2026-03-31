"""!Unit tests for project failure listing endpoint."""

from fastapi import HTTPException

from apps.api.main import JOBS, PROJECTS, list_project_failures


def _seed_failure_jobs() -> None:
    PROJECTS.clear()
    JOBS.clear()
    PROJECTS["p1"] = {"project_id": "p1", "name": "P1"}
    JOBS["j1"] = {
        "job_id": "j1",
        "status": "failed",
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "finished_at": "2026-03-30T00:10:00+00:00",
        "error_message": "boom",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }
    JOBS["j2"] = {
        "job_id": "j2",
        "status": "cancelled",
        "submitted_at": "2026-03-30T00:01:00+00:00",
        "finished_at": "2026-03-30T00:02:00+00:00",
        "cancel_reason": "manual stop",
        "payload": {"project_id": "p1", "site_id": "s2"},
        "events": [],
    }
    JOBS["j3"] = {
        "job_id": "j3",
        "status": "queued",
        "submitted_at": "2026-03-30T00:03:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s3"},
        "events": [],
    }
    JOBS["j4"] = {
        "job_id": "j4",
        "status": "queued",
        "submitted_at": "2026-03-30T00:04:00+00:00",
        "retry_of": "j1",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }


def test_failures_listing_includes_failed_and_cancelled() -> None:
    """!Failure listing should include expected statuses and metadata."""
    _seed_failure_jobs()
    result = list_project_failures("p1", include_cancelled=True, limit=10, offset=0)

    assert result["count"] == 2
    assert result["returned"] == 2
    assert result["failures"][0]["job_id"] == "j1"
    assert result["failures"][0]["has_retry_child"] is True
    assert result["failures"][1]["job_id"] == "j2"
    assert result["failures"][1]["cancel_reason"] == "manual stop"


def test_failures_listing_can_exclude_cancelled() -> None:
    """!Cancelled jobs should be omitted when include_cancelled is false."""
    _seed_failure_jobs()
    result = list_project_failures("p1", include_cancelled=False, limit=10, offset=0)
    assert result["count"] == 1
    assert result["failures"][0]["status"] == "failed"


def test_failures_listing_validates_paging() -> None:
    """!Invalid paging parameters should return 400."""
    _seed_failure_jobs()
    try:
        list_project_failures("p1", limit=0, offset=0)
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected HTTPException for invalid limit")
