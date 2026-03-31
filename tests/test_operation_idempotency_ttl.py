"""!Unit tests for operation idempotency TTL pruning."""

from apps.api import main


def test_prune_operation_idempotency_drops_expired_and_invalid_entries(monkeypatch) -> None:
    """!TTL prune should remove stale/invalid entries and keep recent ones."""
    from datetime import datetime, timezone

    main.OPERATION_IDEMPOTENCY.clear()
    main.OPERATION_IDEMPOTENCY.update(
        {
            "recent": {
                "response": {"ok": True},
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            "old": {
                "response": {"ok": False},
                "created_at": "2020-01-01T00:00:00+00:00",
            },
            "broken": {"response": {"ok": False}, "created_at": "not-a-time"},
        }
    )
    monkeypatch.setattr(main, "OPERATION_IDEMPOTENCY_TTL_SECONDS", 60 * 60 * 24 * 365)

    main._prune_operation_idempotency()

    assert "recent" in main.OPERATION_IDEMPOTENCY
    assert "old" not in main.OPERATION_IDEMPOTENCY
    assert "broken" not in main.OPERATION_IDEMPOTENCY
