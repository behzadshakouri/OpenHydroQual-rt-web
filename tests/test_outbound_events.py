"""!Unit tests for outbound webhook notifications."""

import json
from urllib.error import URLError

from apps.api import main


def test_notify_external_returns_false_without_url(monkeypatch) -> None:
    """!No webhook URL configured should short-circuit without errors."""
    monkeypatch.setattr(main, "OUTBOUND_WEBHOOK_URL", "")
    assert main._notify_external("job.queued", "sim_1", "queued") is False


def test_notify_external_posts_payload(monkeypatch) -> None:
    """!Configured webhook should receive a structured JSON event body."""
    monkeypatch.setattr(main, "OUTBOUND_WEBHOOK_URL", "https://example.com/webhook")
    monkeypatch.setattr(main, "OUTBOUND_WEBHOOK_TOKEN", "token-123")

    captured: dict = {}

    class _FakeResponse:
        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

    def _fake_urlopen(req, timeout):  # noqa: ANN001
        captured["timeout"] = timeout
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["auth"] = req.headers.get("Authorization")
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr(main.urlrequest, "urlopen", _fake_urlopen)
    ok = main._notify_external("job.completed", "sim_2", "completed", payload={"k": "v"})

    assert ok is True
    assert captured["url"] == "https://example.com/webhook"
    assert captured["method"] == "POST"
    assert captured["auth"] == "Bearer token-123"
    assert captured["timeout"] == 3
    assert captured["body"]["event_type"] == "job.completed"
    assert captured["body"]["job_id"] == "sim_2"
    assert captured["body"]["status"] == "completed"
    assert captured["body"]["payload"] == {"k": "v"}


def test_notify_external_handles_transport_error(monkeypatch) -> None:
    """!Transport failures should be swallowed and reported as False."""
    monkeypatch.setattr(main, "OUTBOUND_WEBHOOK_URL", "https://example.com/webhook")

    def _fake_urlopen(req, timeout):  # noqa: ANN001
        raise URLError("network down")

    monkeypatch.setattr(main.urlrequest, "urlopen", _fake_urlopen)
    assert main._notify_external("job.failed", "sim_3", "failed") is False
