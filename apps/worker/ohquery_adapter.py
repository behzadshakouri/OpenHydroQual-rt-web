"""!Adapter helpers for invoking OHQuery calculation endpoints."""

import os
import shlex
import subprocess
from typing import Any

import requests


DEFAULT_OHQUERY_BASE_URL = "http://localhost:8080"
DEFAULT_OHQUERY_TIMEOUT_SECONDS = 30.0


def _ohquery_base_url() -> str:
    return os.getenv("OHQUERY_BASE_URL", DEFAULT_OHQUERY_BASE_URL)


def _ohquery_timeout_seconds() -> float:
    return float(os.getenv("OHQUERY_TIMEOUT_SECONDS", str(DEFAULT_OHQUERY_TIMEOUT_SECONDS)))


def _openhydroqual_cmd() -> str:
    return os.getenv("OPENHYDROQUAL_CMD", "").strip()


class OHQueryExecutionError(RuntimeError):
    """!Normalized execution error that includes a stable error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def run_ohquery_calculation(parameters: dict[str, Any]) -> dict[str, Any]:
    """!Call OHQuery /calculate endpoint and return JSON output.

    Expected OHQuery service behavior is based on existing terminal/OHQuery server implementation.
    """
    timeout_seconds = _ohquery_timeout_seconds()
    openhydroqual_cmd = _openhydroqual_cmd()
    ohquery_base_url = _ohquery_base_url()

    if openhydroqual_cmd:
        command = shlex.split(openhydroqual_cmd)
        cli_args = parameters.get("cli_args", [])
        if isinstance(cli_args, list):
            command.extend(str(arg) for arg in cli_args)
        script_path = (
            parameters.get("script_path")
            or parameters.get("ohq_script_path")
            or parameters.get("ohq_file")
        )
        if script_path:
            command.append(str(script_path))
        try:
            run = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OHQueryExecutionError(
                "engine_timeout",
                f"OpenHydroQual command timed out after {timeout_seconds} seconds",
            ) from exc
        if run.returncode != 0:
            raise OHQueryExecutionError(
                "engine_exit_nonzero",
                f"OpenHydroQual command failed (exit={run.returncode}): {run.stderr.strip() or run.stdout.strip()}"
            )
        return {
            "engine": "OpenHydroQualCLI",
            "command": command,
            "returncode": run.returncode,
            "stdout": run.stdout,
            "stderr": run.stderr,
        }

    try:
        response = requests.post(
            f"{ohquery_base_url.rstrip('/')}/calculate",
            json=parameters,
            timeout=timeout_seconds,
        )
    except requests.Timeout as exc:
        raise OHQueryExecutionError(
            "engine_timeout",
            f"OHQuery HTTP call timed out after {timeout_seconds} seconds",
        ) from exc
    except requests.RequestException as exc:
        raise OHQueryExecutionError(
            "engine_unreachable",
            f"OHQuery HTTP call failed: {exc}",
        ) from exc

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise OHQueryExecutionError(
            "engine_http_error",
            f"OHQuery returned HTTP {response.status_code}",
        ) from exc

    try:
        return response.json()
    except ValueError as exc:
        raise OHQueryExecutionError(
            "engine_invalid_response",
            "OHQuery returned a non-JSON response payload",
        ) from exc
