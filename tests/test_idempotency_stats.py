"""!Unit tests for idempotency cache stats endpoint."""

from apps.api import main


def test_idempotency_stats_reports_entry_count_and_ages(monkeypatch) -> None:
    """!Stats endpoint should expose count and age metrics for operation idempotency."""
    main.OPERATION_IDEMPOTENCY.clear()
    main.OPERATION_IDEMPOTENCY.update(
        {
            "k1": {"response": {"ok": 1}, "created_at": "2026-03-30T00:00:00+00:00"},
            "k2": {"response": {"ok": 2}, "created_at": "2026-03-30T00:10:00+00:00"},
        }
    )
    monkeypatch.setattr(main, "OPERATION_IDEMPOTENCY_TTL_SECONDS", 10_000_000)
    stats = main.get_idempotency_stats()

    assert stats["operation_idempotency_entries"] == 2
    assert stats["oldest_entry_age_seconds"] is not None
    assert stats["newest_entry_age_seconds"] is not None
    assert stats["average_entry_age_seconds"] is not None


def test_idempotency_stats_prunes_invalid_entries() -> None:
    """!Stats call should prune malformed idempotency entries before reporting."""
    main.OPERATION_IDEMPOTENCY.clear()
    main.OPERATION_IDEMPOTENCY["bad"] = {"response": {"ok": 0}, "created_at": "not-a-time"}
    stats = main.get_idempotency_stats()
    assert stats["operation_idempotency_entries"] == 0
