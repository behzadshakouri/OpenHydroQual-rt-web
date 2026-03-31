"""!Unit tests for project-level bulk retry endpoint."""

from fastapi import HTTPException
from pydantic import ValidationError

from apps.api.main import BulkRetryRequest, JOBS, PROJECTS, retry_project_simulations


def _seed_project_jobs() -> None:
    PROJECTS.clear()
    JOBS.clear()
    PROJECTS["p1"] = {"project_id": "p1", "name": "P1"}
    JOBS["j1"] = {
        "job_id": "j1",
        "status": "failed",
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }
    JOBS["j2"] = {
        "job_id": "j2",
        "status": "cancelled",
        "submitted_at": "2026-03-30T00:01:00+00:00",
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


def test_bulk_retry_matches_statuses_and_limit() -> None:
    """!Bulk retry should only retry selected statuses up to limit."""
    _seed_project_jobs()
    result = retry_project_simulations("p1", BulkRetryRequest(statuses=["failed", "cancelled"], limit=1))

    assert result["matched_jobs"] == 2
    assert result["retried_jobs"] == 1
    retry = result["retries"][0]
    assert retry["retry_of"] == "j1"
    assert retry["job_id"] in JOBS
    assert JOBS[retry["job_id"]]["status"] == "queued"


def test_bulk_retry_requires_existing_project() -> None:
    """!Unknown projects should return 404."""
    PROJECTS.clear()
    JOBS.clear()
    try:
        retry_project_simulations("missing", BulkRetryRequest())
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException for missing project")


def test_bulk_retry_validates_payload() -> None:
    """!Model validation should reject empty statuses and invalid limit."""
    try:
        BulkRetryRequest(statuses=[], limit=1)
    except ValidationError as exc:
        assert "statuses" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for empty statuses")

    try:
        BulkRetryRequest(statuses=["failed"], limit=0)
    except ValidationError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for invalid limit")
