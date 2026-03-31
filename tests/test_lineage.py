"""!Unit tests for simulation retry lineage endpoint."""

from fastapi import HTTPException

from apps.api.main import JOBS, get_simulation_lineage


def _seed_lineage_jobs() -> None:
    JOBS.clear()
    JOBS["j1"] = {
        "job_id": "j1",
        "status": "failed",
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }
    JOBS["j2"] = {
        "job_id": "j2",
        "status": "failed",
        "retry_of": "j1",
        "submitted_at": "2026-03-30T00:05:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }
    JOBS["j3"] = {
        "job_id": "j3",
        "status": "completed",
        "retry_of": "j2",
        "submitted_at": "2026-03-30T00:10:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }


def test_lineage_returns_parent_chain_to_root() -> None:
    """!Lineage should include current job and ancestors to root."""
    _seed_lineage_jobs()
    result = get_simulation_lineage("j3")

    assert result["root_job_id"] == "j1"
    assert [item["job_id"] for item in result["lineage_chain"]] == ["j3", "j2", "j1"]


def test_lineage_returns_immediate_children() -> None:
    """!Lineage should include direct children for operator navigation."""
    _seed_lineage_jobs()
    result = get_simulation_lineage("j2")

    assert result["root_job_id"] == "j1"
    assert len(result["children"]) == 1
    assert result["children"][0]["job_id"] == "j3"


def test_lineage_requires_existing_job() -> None:
    """!Missing job should return 404."""
    JOBS.clear()
    try:
        get_simulation_lineage("missing")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException for missing lineage job")
