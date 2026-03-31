"""!Unit tests for system state snapshot endpoint."""

from apps.api.main import (
    IDEMPOTENCY_INDEX,
    JOBS,
    METRICS,
    OPERATION_IDEMPOTENCY,
    PROJECTS,
    SITES,
    WEBHOOK_AUDIT,
    get_system_state_snapshot,
)


def test_system_state_snapshot_reports_counts() -> None:
    """!Snapshot should include store counts and job status breakdown."""
    PROJECTS.clear()
    SITES.clear()
    JOBS.clear()
    IDEMPOTENCY_INDEX.clear()
    OPERATION_IDEMPOTENCY.clear()
    WEBHOOK_AUDIT.clear()
    METRICS["jobs_created_total"] = 0

    PROJECTS["p1"] = {"project_id": "p1", "name": "P1"}
    SITES["p1:s1"] = {"project_id": "p1", "site_id": "s1"}
    JOBS["j1"] = {"job_id": "j1", "status": "queued", "payload": {"project_id": "p1", "site_id": "s1"}}
    JOBS["j2"] = {"job_id": "j2", "status": "failed", "payload": {"project_id": "p1", "site_id": "s1"}}
    IDEMPOTENCY_INDEX["key1"] = "j1"
    OPERATION_IDEMPOTENCY["op1"] = {"response": {"ok": True}, "created_at": "2026-03-30T00:00:00+00:00"}
    WEBHOOK_AUDIT.append({"event_type": "job.failed"})
    METRICS["jobs_created_total"] = 2

    snapshot = get_system_state_snapshot()
    assert snapshot["projects_total"] == 1
    assert snapshot["sites_total"] == 1
    assert snapshot["jobs_total"] == 2
    assert snapshot["job_status_counts"]["queued"] == 1
    assert snapshot["job_status_counts"]["failed"] == 1
    assert snapshot["idempotency_keys_total"] == 1
    assert snapshot["operation_idempotency_total"] == 1
    assert snapshot["webhook_audit_total"] == 1
    assert snapshot["metrics"]["jobs_created_total"] == 2
