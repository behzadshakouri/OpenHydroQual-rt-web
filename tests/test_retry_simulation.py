"""!Unit tests for retry simulation endpoint behavior."""

from fastapi import HTTPException

from apps.api.main import JOBS, RetrySimulationRequest, retry_simulation


def _seed_job(job_id: str, status: str) -> None:
    JOBS.clear()
    JOBS[job_id] = {
        "job_id": job_id,
        "status": status,
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "payload": {
            "project_id": "p1",
            "site_id": "s1",
            "facility_type": "drywell",
            "time_window": {"start_utc": "2026-03-30T00:00:00Z", "end_utc": "2026-03-30T01:00:00Z"},
            "forcing_ref": {"dataset_id": "demo"},
            "parameters_ref": {"profile_id": "default"},
            "request_contract": "simulation_request.v1",
        },
        "events": [{"at": "2026-03-30T00:00:00+00:00", "status": status}],
    }


def test_retry_simulation_creates_child_job() -> None:
    """!Retry should enqueue a new queued job linked to original job."""
    _seed_job("sim_done", "failed")
    result = retry_simulation("sim_done", RetrySimulationRequest(force=False))

    assert result["status"] == "queued"
    assert result["retry_of"] == "sim_done"
    new_job_id = result["job_id"]
    assert new_job_id in JOBS
    assert JOBS[new_job_id]["retry_of"] == "sim_done"
    assert JOBS[new_job_id]["payload"]["site_id"] == "s1"
    assert any(evt["status"] == "retried" for evt in JOBS["sim_done"]["events"])


def test_retry_rejects_active_jobs_without_force() -> None:
    """!Active jobs should not be retried unless force is true."""
    _seed_job("sim_active", "running")
    try:
        retry_simulation("sim_active", RetrySimulationRequest(force=False))
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "force=true" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for active retry")


def test_retry_allows_force_on_active_jobs() -> None:
    """!Force retry can clone active jobs when requested by operator."""
    _seed_job("sim_active", "queued")
    result = retry_simulation("sim_active", RetrySimulationRequest(force=True))
    assert result["original_status"] == "queued"
    assert result["job_id"] in JOBS
