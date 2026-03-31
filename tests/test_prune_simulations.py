"""!Unit tests for project simulation pruning endpoint."""

from datetime import datetime, timezone

from apps.api.main import JOBS, PROJECTS, PruneSimulationsRequest, prune_project_simulations


def _seed_prune_jobs() -> None:
    PROJECTS.clear()
    JOBS.clear()
    PROJECTS["p1"] = {"project_id": "p1", "name": "P1"}
    JOBS["j1"] = {
        "job_id": "j1",
        "status": "completed",
        "submitted_at": "2026-03-29T00:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }
    JOBS["j2"] = {
        "job_id": "j2",
        "status": "failed",
        "submitted_at": "2026-03-29T01:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s2"},
        "events": [],
    }
    JOBS["j3"] = {
        "job_id": "j3",
        "status": "queued",
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s3"},
        "events": [],
    }


def test_prune_dry_run_returns_candidates_without_deleting() -> None:
    """!Dry-run pruning should identify candidates but not mutate state."""
    _seed_prune_jobs()
    result = prune_project_simulations(
        "p1",
        PruneSimulationsRequest(
            statuses=["completed", "failed"],
            before_utc=datetime(2026, 3, 30, tzinfo=timezone.utc),
            dry_run=True,
            limit=10,
        ),
    )
    assert result["candidate_jobs"] == 2
    assert result["deleted_jobs"] == 0
    assert "j1" in JOBS and "j2" in JOBS


def test_prune_executes_deletion_when_not_dry_run() -> None:
    """!Non-dry prune should delete matching jobs."""
    _seed_prune_jobs()
    result = prune_project_simulations(
        "p1",
        PruneSimulationsRequest(
            statuses=["completed", "failed"],
            before_utc=datetime(2026, 3, 30, tzinfo=timezone.utc),
            dry_run=False,
            limit=1,
        ),
    )
    assert result["candidate_jobs"] == 1
    assert result["deleted_jobs"] == 1
    assert len(JOBS) == 2


def test_prune_filters_by_status() -> None:
    """!Status filters should restrict prune candidates."""
    _seed_prune_jobs()
    result = prune_project_simulations(
        "p1",
        PruneSimulationsRequest(statuses=["failed"], dry_run=True, limit=10),
    )
    assert result["candidate_jobs"] == 1
    assert result["job_ids"] == ["j2"]
