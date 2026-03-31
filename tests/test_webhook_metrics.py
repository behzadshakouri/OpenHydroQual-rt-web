"""!Unit tests for outbound webhook success/failure metric counters."""

from urllib.error import URLError

from apps.api import main


def test_notify_external_increments_success_metric(monkeypatch) -> None:
    """!Successful webhook sends should increment success counter."""
    monkeypatch.setattr(main, "OUTBOUND_WEBHOOK_URL", "https://example.com/webhook")
    main.METRICS["webhook_notify_success_total"] = 0
    main.METRICS["webhook_notify_failure_total"] = 0

    class _FakeResponse:
        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

    monkeypatch.setattr(main.urlrequest, "urlopen", lambda req, timeout: _FakeResponse())
    assert main._notify_external("job.started", "sim_1", "running") is True
    assert main.METRICS["webhook_notify_success_total"] == 1
    assert main.METRICS["webhook_notify_failure_total"] == 0


def test_notify_external_increments_failure_metric(monkeypatch) -> None:
    """!Failed webhook sends should increment failure counter."""
    monkeypatch.setattr(main, "OUTBOUND_WEBHOOK_URL", "https://example.com/webhook")
    main.METRICS["webhook_notify_success_total"] = 0
    main.METRICS["webhook_notify_failure_total"] = 0

    def _raise(*args, **kwargs):  # noqa: ANN002, ANN003
        raise URLError("network")

    monkeypatch.setattr(main.urlrequest, "urlopen", _raise)
    assert main._notify_external("job.failed", "sim_2", "failed") is False
    assert main.METRICS["webhook_notify_success_total"] == 0
    assert main.METRICS["webhook_notify_failure_total"] == 1
