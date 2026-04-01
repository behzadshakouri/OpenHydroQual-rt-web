"""!Worker contract tests for scaffold simulation task behavior."""

from datetime import datetime

from apps.worker import tasks
from apps.worker.tasks import run_simulation


def test_worker_mock_mode() -> None:
    """!Validate mock-mode worker payload shape and required result fields."""
    result = run_simulation({"job_id": "sim_1", "payload": {"project_id": "la-drywell-pilot"}})

    assert result["job_id"] == "sim_1"
    assert result["status"] == "completed"
    assert result["result_contract"] == "simulation_result.v1"
    assert result["adapter"]["engine"] == "OHQuery"
    assert result["adapter"]["mock"] is True
    assert result["adapter"]["mock_mode"] is True
    assert datetime.fromisoformat(result["generated_at_utc"])
    assert result["metrics"]["peak_depth_m"] == 0.0
    assert result["metrics"]["infiltrated_volume_m3"] == 0.0
    assert result["metrics"]["overflow"] is False


def test_worker_maps_adapter_errors(monkeypatch) -> None:
    """!Worker should emit failed status with deterministic engine error metadata."""
    monkeypatch.setattr(tasks, "MOCK_OHQUERY", False)

    def _fail(_params):  # noqa: ANN001
        raise tasks.OHQueryExecutionError("engine_timeout", "timed out")

    monkeypatch.setattr(tasks, "run_ohquery_calculation", _fail)
    result = run_simulation({"job_id": "sim_2", "payload": {"project_id": "p1"}})

    assert result["job_id"] == "sim_2"
    assert result["status"] == "failed"
    assert result["error"]["code"] == "engine_timeout"
    assert result["adapter"]["raw"]["error_code"] == "engine_timeout"
    assert datetime.fromisoformat(result["generated_at_utc"])
