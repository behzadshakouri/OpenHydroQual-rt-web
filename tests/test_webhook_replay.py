"""!Unit tests for webhook replay endpoint."""

from apps.api import main
from apps.api.main import JOBS, ReplayWebhookRequest, replay_webhook


def _seed_job() -> None:
    JOBS.clear()
    JOBS["j1"] = {
        "job_id": "j1",
        "status": "failed",
        "submitted_at": "2026-03-30T00:00:00+00:00",
        "finished_at": "2026-03-30T00:10:00+00:00",
        "payload": {"project_id": "p1", "site_id": "s1"},
        "events": [],
    }


def test_webhook_replay_uses_default_event_type(monkeypatch) -> None:
    """!Replay should default event type to current job status."""
    _seed_job()
    monkeypatch.setattr(main, "_notify_external", lambda event_type, job_id, status, payload=None: True)
    result = replay_webhook(ReplayWebhookRequest(job_id="j1"))
    assert result["event_type"] == "job.failed"
    assert result["delivered"] is True
    assert result["replay"] is True


def test_webhook_replay_allows_event_override(monkeypatch) -> None:
    """!Replay should support explicit event type overrides."""
    _seed_job()
    captured = {}

    def _fake_notify(event_type, job_id, status, payload=None):  # noqa: ANN001
        captured["event_type"] = event_type
        captured["job_id"] = job_id
        captured["status"] = status
        captured["payload"] = payload
        return False

    monkeypatch.setattr(main, "_notify_external", _fake_notify)
    result = replay_webhook(ReplayWebhookRequest(job_id="j1", event_type="job.manual_replay"))

    assert result["event_type"] == "job.manual_replay"
    assert result["delivered"] is False
    assert captured["payload"]["replay"] is True
