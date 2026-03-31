"""!Unit tests for simulation event polling helper endpoint."""

from fastapi import HTTPException

from apps.api.main import JOBS, poll_simulation_events


def _seed_job(job_id: str, status: str, events: list[dict]) -> None:
    JOBS.clear()
    JOBS[job_id] = {
        "job_id": job_id,
        "status": status,
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": events,
    }


def test_poll_returns_new_events_without_waiting() -> None:
    """!Polling should return immediately when unseen events are available."""
    _seed_job(
        "sim_a",
        "running",
        [
            {"at": "2026-03-30T00:00:00+00:00", "status": "queued"},
            {"at": "2026-03-30T00:01:00+00:00", "status": "running"},
        ],
    )

    result = poll_simulation_events("sim_a", after_index=1, timeout_s=0)
    assert result["count"] == 1
    assert result["events"][0]["status"] == "running"
    assert result["timed_out"] is False


def test_poll_returns_empty_for_finalized_job() -> None:
    """!Polling finalized jobs should return immediately with no timeout."""
    _seed_job("sim_b", "completed", [{"at": "2026-03-30T00:00:00+00:00", "status": "completed"}])

    result = poll_simulation_events("sim_b", after_index=1, timeout_s=5)
    assert result["count"] == 0
    assert result["events"] == []
    assert result["timed_out"] is False
    assert result["status"] == "completed"


def test_poll_times_out_when_no_new_events() -> None:
    """!Polling active jobs can timeout when nothing new appears."""
    _seed_job("sim_c", "running", [{"at": "2026-03-30T00:00:00+00:00", "status": "queued"}])

    result = poll_simulation_events("sim_c", after_index=1, timeout_s=0)
    assert result["count"] == 0
    assert result["events"] == []
    assert result["timed_out"] is True


def test_poll_validates_parameters() -> None:
    """!Input guardrails should reject invalid indexes and timeouts."""
    _seed_job("sim_d", "queued", [])

    try:
        poll_simulation_events("sim_d", after_index=-1, timeout_s=0)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "after_index" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for negative after_index")

    try:
        poll_simulation_events("sim_d", after_index=0, timeout_s=31)
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "timeout_s" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for timeout upper bound")
