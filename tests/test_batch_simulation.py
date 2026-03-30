"""!Unit tests for bulk simulation queue helpers without HTTP client dependency."""

from fastapi import HTTPException

from apps.api.main import (
    JOBS,
    OPERATION_IDEMPOTENCY,
    PROJECTS,
    SITES,
    BatchSimulateRequest,
    trigger_project_simulations,
    trigger_project_simulations_batch,
)


def _seed_project_with_sites(project_id: str, site_ids: list[str]) -> None:
    PROJECTS.clear()
    SITES.clear()
    JOBS.clear()
    OPERATION_IDEMPOTENCY.clear()
    PROJECTS[project_id] = {"project_id": project_id, "name": "Demo"}
    for site_id in site_ids:
        SITES[f"{project_id}:{site_id}"] = {
            "project_id": project_id,
            "site_id": site_id,
            "facility_type": "drywell",
            "latitude": 0.0,
            "longitude": 0.0,
            "metadata": {},
        }


def test_batch_simulation_respects_selected_sites() -> None:
    """!Batch endpoint should enqueue jobs only for selected site identifiers."""
    _seed_project_with_sites("p1", ["s1", "s2", "s3"])

    response = trigger_project_simulations_batch(
        "p1",
        BatchSimulateRequest(site_ids=["s1", "s3"], max_jobs=5),
    )

    assert response["queued_jobs"] == 2
    queued_site_ids = {JOBS[job_id]["payload"]["site_id"] for job_id in response["job_ids"]}
    assert queued_site_ids == {"s1", "s3"}


def test_simulate_all_uses_nonzero_time_window() -> None:
    """!Project simulate-all should set a valid non-zero execution window."""
    _seed_project_with_sites("p2", ["s1"])

    response = trigger_project_simulations("p2")
    assert response["queued_jobs"] == 1
    job = JOBS[response["job_ids"][0]]
    window = job["payload"]["time_window"]
    assert window["start_utc"] < window["end_utc"]


def test_batch_simulation_rejects_over_max_jobs() -> None:
    """!Batch endpoint should fail when selected sites exceed max_jobs."""
    _seed_project_with_sites("p3", ["s1", "s2"])

    try:
        trigger_project_simulations_batch("p3", BatchSimulateRequest(max_jobs=1))
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "max_jobs" in str(exc.detail)
    else:
        raise AssertionError("Expected HTTPException for max_jobs overflow")


def test_batch_simulation_idempotency_replays_response() -> None:
    """!Batch endpoint should replay response for repeated idempotency key."""
    _seed_project_with_sites("p4", ["s1", "s2"])

    first = trigger_project_simulations_batch(
        "p4",
        BatchSimulateRequest(site_ids=["s1"], max_jobs=5),
        x_idempotency_key="batch-key-1",
    )
    second = trigger_project_simulations_batch(
        "p4",
        BatchSimulateRequest(site_ids=["s2"], max_jobs=5),
        x_idempotency_key="batch-key-1",
    )

    assert first["queued_jobs"] == 1
    assert second["idempotent_replay"] is True
    assert second["job_ids"] == first["job_ids"]
