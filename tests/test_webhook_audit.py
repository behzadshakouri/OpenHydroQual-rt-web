"""!Unit tests for webhook audit endpoint and capture behavior."""

from urllib.error import URLError

from apps.api import main


def test_webhook_audit_captures_success_and_failure(monkeypatch) -> None:
    """!Notify helper should append audit rows for both success and failure sends."""
    main.WEBHOOK_AUDIT.clear()
    monkeypatch.setattr(main, "OUTBOUND_WEBHOOK_URL", "https://example.com/webhook")

    class _FakeResponse:
        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

    monkeypatch.setattr(main.urlrequest, "urlopen", lambda req, timeout: _FakeResponse())
    assert main._notify_external("job.started", "sim1", "running") is True

    def _fail(*args, **kwargs):  # noqa: ANN002, ANN003
        raise URLError("down")

    monkeypatch.setattr(main.urlrequest, "urlopen", _fail)
    assert main._notify_external("job.failed", "sim1", "failed") is False

    audit = main.get_webhook_audit(limit=10, only_failures=False)
    assert audit["count"] == 2
    assert audit["items"][0]["success"] is True
    assert audit["items"][1]["success"] is False

    failures = main.get_webhook_audit(limit=10, only_failures=True)
    assert failures["count"] == 1
    assert failures["items"][0]["error"] is not None
