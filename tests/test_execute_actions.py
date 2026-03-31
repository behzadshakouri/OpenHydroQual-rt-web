"""!Unit tests for project action execution endpoint."""

from apps.api.main import (
    ExecuteActionRequest,
    JOBS,
    PROJECTS,
    SITES,
    execute_project_action,
)


def _seed_actions_state() -> None:
    PROJECTS.clear()
    SITES.clear()
    JOBS.clear()
    PROJECTS["p1"] = {"project_id": "p1", "name": "P1"}
    SITES["p1:s1"] = {"project_id": "p1", "site_id": "s1"}
    JOBS["j1"] = {
        "job_id": "j1",
        "status": "failed",
        "submitted_at": "2020-01-01T00:00:00+00:00",
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


def test_execute_requeue_stale_dry_run() -> None:
    """!Execute endpoint should route stale action with dry-run semantics."""
    _seed_actions_state()
    result = execute_project_action(
        "p1",
        ExecuteActionRequest(action="requeue_stale", dry_run=True, stale_after_seconds=10, limit=10),
    )
    assert result["action"] == "requeue_stale"
    assert result["result"]["dry_run"] is True


def test_execute_retry_failures_dry_run_projection() -> None:
    """!Execute endpoint should map retry-failures to dry-run output when requested."""
    _seed_actions_state()
    result = execute_project_action(
        "p1",
        ExecuteActionRequest(action="retry_failures", dry_run=True, limit=10),
    )
    assert result["action"] == "retry_failures"
    assert result["result"]["dry_run"] is True
    assert result["result"]["candidate_jobs"] >= 1
