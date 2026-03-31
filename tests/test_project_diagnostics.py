"""!Unit tests for project diagnostics endpoint."""

from apps.api.main import JOBS, PROJECTS, SITES, get_project_diagnostics


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


def test_project_diagnostics_returns_consolidated_counts() -> None:
    """!Diagnostics should combine summary, timeline, failures and queue stats."""
    _seed_project_data()
    result = get_project_diagnostics("p1", stale_after_seconds=10)
    assert result["project_id"] == "p1"
    assert result["failure_count"] == 1
    assert result["queue_count"] == 1
    assert result["stale_queue_count"] == 1
    assert result["summary"]["total_jobs"] == 2
