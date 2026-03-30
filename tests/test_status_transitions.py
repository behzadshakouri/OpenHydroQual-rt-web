"""!Unit tests for simulation status transition guardrails."""

from fastapi import HTTPException

from apps.api.main import (
    CompletionPayload,
    JOBS,
    cancel_simulation,
    mark_completed,
    mark_started,
)


def _seed_job(job_id: str, status: str) -> None:
    JOBS.clear()
    JOBS[job_id] = {
        "job_id": job_id,
        "status": status,
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [{"at": "2026-03-30T00:00:00+00:00", "status": status}],
    }


def test_finalized_job_cannot_be_restarted() -> None:
    """!Finalized jobs should reject start transitions."""
    _seed_job("sim_final", "completed")
    try:
        mark_started("sim_final")
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "finalized" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException when starting finalized job")


def test_running_job_can_complete() -> None:
    """!Running to completed transition should remain allowed."""
    _seed_job("sim_run", "running")
    result = mark_completed(
        "sim_run",
        CompletionPayload(peak_depth_m=0.1, infiltrated_volume_m3=1.0, overflow=False),
    )
    assert result["status"] == "completed"


def test_invalid_transition_rejected() -> None:
    """!Unknown/current invalid statuses should reject transition requests."""
    _seed_job("sim_unknown", "unknown")
    try:
        cancel_simulation("sim_unknown", reason="cleanup")
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "invalid status transition" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for invalid transition")
