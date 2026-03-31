"""!Unit tests for stale simulation requeue endpoint."""

from apps.api.main import JOBS, PROJECTS, RequeueStaleRequest, requeue_stale_simulations


def _seed_stale_jobs() -> None:
    PROJECTS.clear()
    JOBS.clear()
    PROJECTS["p1"] = {"project_id": "p1", "name": "P1"}
    JOBS["j1"] = {
        "job_id": "j1",
        "status": "queued",
        "submitted_at": "2020-01-01T00:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }
    JOBS["j2"] = {
        "job_id": "j2",
        "status": "running",
        "submitted_at": "2020-01-01T00:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s2"},
        "events": [],
    }
    JOBS["j3"] = {
        "job_id": "j3",
        "status": "completed",
        "submitted_at": "2020-01-01T00:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s3"},
        "events": [],
    }


def test_requeue_stale_dry_run_only_reports_candidates() -> None:
    """!Dry-run stale requeue should not mutate jobs."""
    _seed_stale_jobs()
    result = requeue_stale_simulations("p1", RequeueStaleRequest(dry_run=True, stale_after_seconds=10))
    assert result["candidate_jobs"] == 2
    assert result["requeue_count"] == 0
    assert len(JOBS) == 3


def test_requeue_stale_creates_child_jobs() -> None:
    """!Non-dry stale requeue should enqueue child jobs with retry linkage."""
    _seed_stale_jobs()
    result = requeue_stale_simulations(
        "p1",
        RequeueStaleRequest(dry_run=False, stale_after_seconds=10, include_running=False, limit=10),
    )
    assert result["candidate_jobs"] == 1
    assert result["requeue_count"] == 1
    new_job_id = result["requeues"][0]["job_id"]
    assert JOBS[new_job_id]["retry_of"] == "j1"
    assert any(evt["status"] == "requeued_stale" for evt in JOBS["j1"]["events"])
