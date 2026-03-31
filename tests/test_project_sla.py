"""!Unit tests for project SLA endpoint."""

import pytest
from fastapi import HTTPException

from apps.api.main import JOBS, PROJECTS, SITES, get_project_sla


def _seed_project_data() -> None:
    PROJECTS.clear()
    SITES.clear()
    JOBS.clear()
    PROJECTS["p1"] = {"project_id": "p1", "name": "P1"}
    SITES["p1:s1"] = {"project_id": "p1", "site_id": "s1"}
    JOBS["j1"] = {
        "job_id": "j1",
        "status": "failed",
        "submitted_at": "2020-01-01T00:00:00+00:00",
        "finished_at": "2020-01-01T00:01:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }
    JOBS["j2"] = {
        "job_id": "j2",
        "status": "queued",
        "submitted_at": "2020-01-01T00:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }


def test_project_sla_returns_breaches_and_health() -> None:
    """!SLA response should surface breaches and an unhealthy status when exceeded."""
    _seed_project_data()
    result = get_project_sla(
        "p1",
        max_stale_queue_jobs=0,
        max_failure_rate=0.2,
        stale_after_seconds=10,
    )

    assert result["project_id"] == "p1"
    assert result["observed"]["total_jobs"] == 2
    assert result["observed"]["failed_or_cancelled_jobs"] == 1
    assert result["observed"]["failure_rate"] == 0.5
    assert result["observed"]["stale_queue_jobs"] == 1
    assert result["breaches"] == {"stale_queue_breach": True, "failure_rate_breach": True}
    assert result["is_healthy"] is False


def test_project_sla_validates_threshold_inputs() -> None:
    """!Invalid threshold values should return HTTP 400 validation errors."""
    _seed_project_data()

    with pytest.raises(HTTPException) as stale_err:
        get_project_sla("p1", max_stale_queue_jobs=-1)
    assert stale_err.value.status_code == 400

    with pytest.raises(HTTPException) as rate_err:
        get_project_sla("p1", max_failure_rate=1.5)
    assert rate_err.value.status_code == 400
