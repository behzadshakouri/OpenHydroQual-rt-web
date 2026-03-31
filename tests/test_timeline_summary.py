"""!Unit tests for project-level timeline summary endpoint."""

from fastapi import HTTPException

from apps.api.main import JOBS, PROJECTS, get_project_timeline_summary


def _seed_timeline_jobs() -> None:
    PROJECTS.clear()
    JOBS.clear()
    PROJECTS["p1"] = {"project_id": "p1", "name": "P1"}
    JOBS["j1"] = {
        "job_id": "j1",
        "status": "completed",
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "started_at": "2026-03-30T00:00:10+00:00",
        "finished_at": "2026-03-30T00:01:10+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }
    JOBS["j2"] = {
        "job_id": "j2",
        "status": "completed",
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "started_at": "2026-03-30T00:00:20+00:00",
        "finished_at": "2026-03-30T00:02:20+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }
    JOBS["j3"] = {
        "job_id": "j3",
        "status": "failed",
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "started_at": "2026-03-30T00:00:05+00:00",
        "finished_at": "2026-03-30T00:00:35+00:00",
        "payload": {"project_id": "p1", "site_id": "s2"},
        "events": [],
    }


def test_timeline_summary_aggregates_project_metrics() -> None:
    """!Summary should compute avg and p95 durations across project jobs."""
    _seed_timeline_jobs()
    result = get_project_timeline_summary("p1")

    assert result["total_jobs"] == 3
    assert result["avg_queue_seconds"] == 11.666666666666666
    assert result["avg_run_seconds"] == 70.0
    assert result["avg_total_seconds"] == 81.66666666666667
    assert result["p95_total_seconds"] == 140.0
    assert result["by_site"]["s1"]["count"] == 2


def test_timeline_summary_respects_status_filter() -> None:
    """!Status filter should narrow timeline aggregates."""
    _seed_timeline_jobs()
    result = get_project_timeline_summary("p1", status="failed")
    assert result["total_jobs"] == 1
    assert result["by_site"]["s2"]["count"] == 1


def test_timeline_summary_requires_existing_project() -> None:
    """!Unknown project ids should return 404."""
    PROJECTS.clear()
    JOBS.clear()
    try:
        get_project_timeline_summary("missing")
    except HTTPException as exc:
        assert exc.status_code == 404
    else:
        raise AssertionError("Expected HTTPException for missing project")
