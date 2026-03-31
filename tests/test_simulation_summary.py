"""!Unit tests for project simulation summary endpoint logic."""

from fastapi import HTTPException

from apps.api.main import JOBS, PROJECTS, get_project_simulations_summary


def _seed_jobs() -> None:
    PROJECTS.clear()
    JOBS.clear()
    PROJECTS["p1"] = {"project_id": "p1", "name": "Project 1"}
    JOBS["j1"] = {"job_id": "j1", "status": "completed", "payload": {"project_id": "p1", "site_id": "s1"}}
    JOBS["j2"] = {"job_id": "j2", "status": "failed", "payload": {"project_id": "p1", "site_id": "s1"}}
    JOBS["j3"] = {"job_id": "j3", "status": "queued", "payload": {"project_id": "p1", "site_id": "s2"}}


def test_simulation_summary_aggregates_status_and_site_counts() -> None:
    """!Summary should include by-status and by-site aggregates."""
    _seed_jobs()
    result = get_project_simulations_summary("p1")

    assert result["total_jobs"] == 3
    assert result["completed_jobs"] == 1
    assert result["by_status"]["completed"] == 1
    assert result["by_status"]["failed"] == 1
    assert result["by_site"]["s1"]["total"] == 2
    assert result["by_site"]["s2"]["queued"] == 1


def test_simulation_summary_respects_status_filter() -> None:
    """!Status filter should reduce aggregate scope."""
    _seed_jobs()
    result = get_project_simulations_summary("p1", status="completed")

    assert result["filtered_status"] == "completed"
    assert result["total_jobs"] == 1
    assert result["completion_rate"] == 1.0
    assert list(result["by_status"].keys()) == ["completed"]


def test_simulation_summary_requires_existing_project() -> None:
    """!Unknown project id should raise a 404."""
    PROJECTS.clear()
    JOBS.clear()

    try:
        get_project_simulations_summary("missing")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException for missing project")
