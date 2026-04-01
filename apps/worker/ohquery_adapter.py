"""!Adapter helpers for invoking OHQuery calculation endpoints."""

import os
import shlex
import subprocess
from typing import Any

import requests


OHQUERY_BASE_URL = os.getenv("OHQUERY_BASE_URL", "http://localhost:8080")
OHQUERY_TIMEOUT_SECONDS = float(os.getenv("OHQUERY_TIMEOUT_SECONDS", "30"))
OPENHYDROQUAL_CMD = os.getenv("OPENHYDROQUAL_CMD", "").strip()


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
    if OPENHYDROQUAL_CMD:
        command = shlex.split(OPENHYDROQUAL_CMD)
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
                timeout=OHQUERY_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OHQueryExecutionError(
                "engine_timeout",
                f"OpenHydroQual command timed out after {OHQUERY_TIMEOUT_SECONDS} seconds",
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
            f"{OHQUERY_BASE_URL.rstrip('/')}/calculate",
            json=parameters,
            timeout=OHQUERY_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise OHQueryExecutionError(
            "engine_timeout",
            f"OHQuery HTTP call timed out after {OHQUERY_TIMEOUT_SECONDS} seconds",
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
    except ValueError:
        return {"raw_response": response.text}
