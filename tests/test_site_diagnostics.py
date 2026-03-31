"""!Unit tests for site diagnostics endpoint."""

from apps.api.main import JOBS, PROJECTS, SITES, get_site_diagnostics


def _seed_site_diagnostics_data() -> None:
    PROJECTS.clear()
    SITES.clear()
    JOBS.clear()
    PROJECTS["p1"] = {"project_id": "p1", "name": "P1"}
    SITES["p1:s1"] = {"project_id": "p1", "site_id": "s1"}
    SITES["p1:s2"] = {"project_id": "p1", "site_id": "s2"}
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
    JOBS["j3"] = {
        "job_id": "j3",
        "status": "queued",
        "submitted_at": "2026-03-31T00:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s2"},
        "events": [],
    }


def test_site_diagnostics_returns_site_scoped_counts() -> None:
    """!Site diagnostics should only count failures/queue rows for requested site."""
    _seed_site_diagnostics_data()
    result = get_site_diagnostics("p1", "s1", stale_after_seconds=10)
    assert result["site_id"] == "s1"
    assert result["failure_count"] == 1
    assert result["queue_count"] == 1
    assert result["stale_queue_count"] == 1
    assert result["summary"]["total_jobs"] == 2
