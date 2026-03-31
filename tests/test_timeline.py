"""!Unit tests for simulation timeline endpoint."""

from fastapi import HTTPException

from apps.api.main import JOBS, get_simulation_timeline


def test_timeline_calculates_queue_run_and_total_durations() -> None:
    """!Timeline should compute queue/run/total durations from timestamps."""
    JOBS.clear()
    JOBS["sim_t1"] = {
        "job_id": "sim_t1",
        "status": "completed",
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "started_at": "2026-03-30T00:00:10+00:00",
        "finished_at": "2026-03-30T00:01:40+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }

    result = get_simulation_timeline("sim_t1")
    assert result["queue_seconds"] == 10.0
    assert result["run_seconds"] == 90.0
    assert result["total_seconds"] == 100.0
    assert result["is_finalized"] is True


def test_timeline_handles_missing_fields_gracefully() -> None:
    """!Timeline should return None metrics when timestamps are unavailable."""
    JOBS.clear()
    JOBS["sim_t2"] = {
        "job_id": "sim_t2",
        "status": "queued",
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }
    result = get_simulation_timeline("sim_t2")
    assert result["queue_seconds"] is None
    assert result["run_seconds"] is None
    assert result["total_seconds"] is None
    assert result["is_finalized"] is False


def test_timeline_missing_job_returns_404() -> None:
    """!Timeline should reject unknown jobs."""
    JOBS.clear()
    try:
        get_simulation_timeline("missing")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException for missing job")
