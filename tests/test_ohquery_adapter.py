"""!Unit tests for OHQuery adapter execution paths."""

from types import SimpleNamespace

from apps.worker import ohquery_adapter


def test_adapter_runs_openhydroqual_cli(monkeypatch) -> None:
    """!Verify adapter can execute OpenHydroQual CLI command when configured."""
    monkeypatch.setattr(ohquery_adapter, "OPENHYDROQUAL_CMD", "OpenHydroQualCLI")

    def _fake_run(command, capture_output, text, timeout, check):  # noqa: ANN001
        assert "OpenHydroQualCLI" in command[0]
        assert "--quiet" in command
        assert "/tmp/starter_generated.ohq" in command
        assert capture_output is True
        assert text is True
        assert check is False
        assert timeout == ohquery_adapter.OHQUERY_TIMEOUT_SECONDS
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(ohquery_adapter.subprocess, "run", _fake_run)
    result = ohquery_adapter.run_ohquery_calculation(
        {
            "script_path": "/tmp/starter_generated.ohq",
            "cli_args": ["--quiet"],
        }
    )

    assert result["engine"] == "OpenHydroQualCLI"
    assert result["returncode"] == 0


def test_adapter_maps_cli_timeout(monkeypatch) -> None:
    """!Verify CLI timeout is converted to normalized adapter error."""
    monkeypatch.setattr(ohquery_adapter, "OPENHYDROQUAL_CMD", "OpenHydroQualCLI")

    def _fake_run(command, capture_output, text, timeout, check):  # noqa: ANN001
        raise ohquery_adapter.subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(ohquery_adapter.subprocess, "run", _fake_run)

    try:
        ohquery_adapter.run_ohquery_calculation({"script_path": "/tmp/in.ohq"})
    except ohquery_adapter.OHQueryExecutionError as exc:
        assert exc.code == "engine_timeout"
    else:
        raise AssertionError("expected OHQueryExecutionError")


def test_adapter_maps_invalid_http_payload(monkeypatch) -> None:
    """!Verify non-JSON HTTP responses are surfaced as normalized adapter errors."""
    monkeypatch.setattr(ohquery_adapter, "OPENHYDROQUAL_CMD", "")

    class _FakeResponse:
        status_code = 200
        text = "<html>bad gateway</html>"

        def raise_for_status(self) -> None:
            return None

        def json(self):  # noqa: ANN201
            raise ValueError("not json")

    monkeypatch.setattr(ohquery_adapter.requests, "post", lambda *args, **kwargs: _FakeResponse())

    try:
        ohquery_adapter.run_ohquery_calculation({"project_id": "p1"})
    except ohquery_adapter.OHQueryExecutionError as exc:
        assert exc.code == "engine_invalid_response"
    else:
        raise AssertionError("expected OHQueryExecutionError")
