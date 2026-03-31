"""!Unit tests for site-level simulation summary endpoint."""

from fastapi import HTTPException

from apps.api.main import JOBS, PROJECTS, SITES, get_site_simulations_summary


def _seed_site_jobs() -> None:
    PROJECTS.clear()
    SITES.clear()
    JOBS.clear()
    PROJECTS["p1"] = {"project_id": "p1", "name": "Project 1"}
    SITES["p1:s1"] = {"project_id": "p1", "site_id": "s1", "facility_type": "drywell"}
    SITES["p1:s2"] = {"project_id": "p1", "site_id": "s2", "facility_type": "drywell"}
    JOBS["j1"] = {"job_id": "j1", "status": "completed", "payload": {"project_id": "p1", "site_id": "s1"}}
    JOBS["j2"] = {"job_id": "j2", "status": "failed", "payload": {"project_id": "p1", "site_id": "s1"}}
    JOBS["j3"] = {"job_id": "j3", "status": "queued", "payload": {"project_id": "p1", "site_id": "s2"}}


def test_site_summary_aggregates_single_site() -> None:
    """!Site summary should only include jobs for the requested site."""
    _seed_site_jobs()
    result = get_site_simulations_summary("p1", "s1")
    assert result["total_jobs"] == 2
    assert result["completed_jobs"] == 1
    assert result["by_status"]["failed"] == 1
    assert "queued" not in result["by_status"]


def test_site_summary_respects_status_filter() -> None:
    """!Status filter should narrow site-level aggregate scope."""
    _seed_site_jobs()
    result = get_site_simulations_summary("p1", "s1", status="completed")
    assert result["total_jobs"] == 1
    assert result["completion_rate"] == 1.0
    assert result["by_status"] == {"completed": 1}


def test_site_summary_requires_existing_site() -> None:
    """!Missing site should return 404."""
    _seed_site_jobs()
    try:
        get_site_simulations_summary("p1", "missing")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException for missing site")
