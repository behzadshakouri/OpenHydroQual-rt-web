"""!Unit tests for project recommended-actions endpoint."""

from apps.api.main import JOBS, PROJECTS, SITES, get_project_actions


def _seed_actions_data() -> None:
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


def test_project_actions_suggests_requeue_and_retry() -> None:
    """!Actions endpoint should recommend stale requeue and failure retry when applicable."""
    _seed_actions_data()
    result = get_project_actions("p1", stale_after_seconds=10)
    action_names = [item["action"] for item in result["recommended_actions"]]
    assert "requeue_stale" in action_names
    assert "retry_failures" in action_names
