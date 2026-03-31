"""!Unit tests for system maintenance cleanup endpoint."""

from apps.api.main import (
    MaintenanceCleanupRequest,
    OPERATION_IDEMPOTENCY,
    WEBHOOK_AUDIT,
    cleanup_system_state,
)


def _seed_system_state() -> None:
    WEBHOOK_AUDIT.clear()
    OPERATION_IDEMPOTENCY.clear()
    WEBHOOK_AUDIT.extend([{"event_type": "a"}, {"event_type": "b"}])
    OPERATION_IDEMPOTENCY.update({"k1": {"response": {}}, "k2": {"response": {}}})


def test_cleanup_dry_run_does_not_mutate_state() -> None:
    """!Dry-run cleanup should only report before/after without mutation."""
    _seed_system_state()
    result = cleanup_system_state(
        MaintenanceCleanupRequest(
            clear_webhook_audit=True,
            clear_operation_idempotency=True,
            dry_run=True,
        )
    )
    assert result["before"]["webhook_audit_entries"] == 2
    assert result["after"]["webhook_audit_entries"] == 2
    assert len(WEBHOOK_AUDIT) == 2
    assert len(OPERATION_IDEMPOTENCY) == 2


def test_cleanup_executes_requested_mutations() -> None:
    """!Non-dry cleanup should clear selected stores."""
    _seed_system_state()
    result = cleanup_system_state(
        MaintenanceCleanupRequest(
            clear_webhook_audit=True,
            clear_operation_idempotency=False,
            dry_run=False,
        )
    )
    assert result["before"]["webhook_audit_entries"] == 2
    assert result["after"]["webhook_audit_entries"] == 0
    assert len(WEBHOOK_AUDIT) == 0
    assert len(OPERATION_IDEMPOTENCY) == 2
