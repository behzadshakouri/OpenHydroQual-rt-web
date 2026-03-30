"""!Scaffold FastAPI API service for OpenHydroQual real-time orchestration."""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from threading import Lock
import time
from typing import Literal
from urllib import request as urlrequest
from urllib.error import URLError
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field, model_validator

from .queue import enqueue_run


app = FastAPI(title="OHQ Real-time API", version="0.2.0")

JOBS: dict[str, dict] = {}
IDEMPOTENCY_INDEX: dict[str, str] = {}
LOCK = Lock()
PROJECTS: dict[str, dict] = {}
SITES: dict[str, dict] = {}
STATE_FILE = Path(os.getenv("STATE_FILE", "./ohq_rt_state.json"))
ENABLE_FILE_STATE = os.getenv("ENABLE_FILE_STATE", "false").lower() == "true"
METRICS: dict[str, int] = {
    "jobs_created_total": 0,
    "jobs_completed_total": 0,
    "projects_created_total": 0,
    "sites_created_total": 0,
    "jobs_failed_total": 0,
    "jobs_cancelled_total": 0,
}
OUTBOUND_WEBHOOK_URL = os.getenv("OUTBOUND_WEBHOOK_URL", "").strip()
OUTBOUND_WEBHOOK_TOKEN = os.getenv("OUTBOUND_WEBHOOK_TOKEN", "").strip()


def _load_state() -> None:
    """!Load persisted scaffold state from disk when enabled."""
    if not ENABLE_FILE_STATE or not STATE_FILE.exists():
        return
    try:
        payload = json.loads(STATE_FILE.read_text())
        JOBS.update(payload.get("jobs", {}))
        IDEMPOTENCY_INDEX.update(payload.get("idempotency_index", {}))
        PROJECTS.update(payload.get("projects", {}))
        SITES.update(payload.get("sites", {}))
    except (OSError, json.JSONDecodeError):
        # Best-effort bootstrap for scaffold; production should log and alert.
        return


def _persist_state() -> None:
    """!Persist in-memory scaffold state to disk when enabled."""
    if not ENABLE_FILE_STATE:
        return
    STATE_FILE.write_text(
        json.dumps(
            {
                "jobs": JOBS,
                "idempotency_index": IDEMPOTENCY_INDEX,
                "projects": PROJECTS,
                "sites": SITES,
            }
        )
    )


def _notify_external(event_type: str, job_id: str, status: str, payload: dict | None = None) -> bool:
    """!Best-effort outbound event notification for AWS/webhook integrations."""
    if not OUTBOUND_WEBHOOK_URL:
        return False

    body = {
        "source": "openhydroqual-rt-api",
        "event_type": event_type,
        "job_id": job_id,
        "status": status,
        "sent_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    if payload:
        body["payload"] = payload

    headers = {"Content-Type": "application/json"}
    if OUTBOUND_WEBHOOK_TOKEN:
        headers["Authorization"] = f"Bearer {OUTBOUND_WEBHOOK_TOKEN}"

    req = urlrequest.Request(
        OUTBOUND_WEBHOOK_URL,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=3):  # nosec B310 - controlled integration URL
            return True
    except (URLError, TimeoutError, OSError):
        return False


_load_state()


class TimeWindow(BaseModel):
    """!Time range for a simulation request."""
    start_utc: datetime
    end_utc: datetime

    @model_validator(mode="after")
    def validate_range(self) -> "TimeWindow":
        """!Validate that end_utc is strictly later than start_utc."""
        if self.end_utc <= self.start_utc:
            raise ValueError("end_utc must be later than start_utc")
        return self


class RefPayload(BaseModel):
    """!Reference object for forcing or parameter dataset/profile pointers."""
    dataset_id: str | None = None
    version: str | None = None
    profile_id: str | None = None


class SimulationRequest(BaseModel):
    """!API payload for creating a simulation job."""
    project_id: str
    site_id: str
    facility_type: str
    time_window: TimeWindow
    forcing_ref: RefPayload
    parameters_ref: RefPayload
    request_contract: Literal["simulation_request.v1"] = "simulation_request.v1"


class CompletionPayload(BaseModel):
    """!Manual completion metrics payload for a simulation job."""
    peak_depth_m: float
    infiltrated_volume_m3: float
    overflow: bool


class ProjectCreate(BaseModel):
    """!Payload for creating a project record."""
    project_id: str
    name: str


class ProjectCloneRequest(BaseModel):
    """!Payload for cloning an existing project."""
    new_project_id: str
    new_name: str


class ProjectImportRequest(BaseModel):
    """!Payload for importing project, site, and job records."""
    project: dict
    sites: list[dict] = Field(default_factory=list)
    jobs: list[dict] = Field(default_factory=list)


class SiteCreate(BaseModel):
    """!Payload for creating a site under a project."""
    site_id: str
    facility_type: str
    latitude: float
    longitude: float
    metadata: dict = Field(default_factory=dict)


class ResultMetrics(BaseModel):
    """!Normalized result metrics for simulation outcomes."""
    peak_depth_m: float
    infiltrated_volume_m3: float
    overflow: bool


class AdapterMetadata(BaseModel):
    """!Metadata emitted by the adapter/worker with simulation results."""
    engine: str
    mock: bool
    mock_mode: bool
    raw: dict = Field(default_factory=dict)
    base_url: str | None = None


class WorkerResultPayload(BaseModel):
    """!Internal callback payload submitted by workers when jobs finish."""
    status: Literal["completed", "failed"] = "completed"
    result_contract: Literal["simulation_result.v1"] = "simulation_result.v1"
    metrics: ResultMetrics
    adapter: AdapterMetadata
    generated_at_utc: datetime | None = None


class BatchSimulateRequest(BaseModel):
    """!Payload for queueing project simulations in bulk."""
    site_ids: list[str] | None = None
    time_window: TimeWindow | None = None
    forcing_ref: RefPayload = Field(default_factory=lambda: RefPayload(dataset_id="scheduled"))
    parameters_ref: RefPayload = Field(default_factory=lambda: RefPayload(profile_id="default"))
    max_jobs: int = 1000

    @model_validator(mode="after")
    def validate_max_jobs(self) -> "BatchSimulateRequest":
        """!Validate that batch max_jobs is positive."""
        if self.max_jobs < 1:
            raise ValueError("max_jobs must be >= 1")
        return self


class RetrySimulationRequest(BaseModel):
    """!Payload for retrying a prior simulation job."""
    force: bool = False


@app.get("/health")
def health() -> dict:
    """!Return a lightweight health payload."""
    return {"status": "ok", "service": "api", "version": "0.2.0"}


@app.get("/metrics")
def metrics() -> Response:
    """!Expose Prometheus-style counter metrics."""
    lines = [f"{k} {v}" for k, v in METRICS.items()]
    body = "\n".join(lines) + "\n"
    return Response(content=body, media_type="text/plain; version=0.0.4")

@app.post("/v1/projects")
def create_project(payload: ProjectCreate) -> dict:
    """!Create a project resource."""
    with LOCK:
        if payload.project_id in PROJECTS:
            raise HTTPException(status_code=409, detail="project already exists")
        PROJECTS[payload.project_id] = payload.model_dump()
        METRICS["projects_created_total"] += 1
        _persist_state()
    return PROJECTS[payload.project_id]


@app.post("/v1/projects/import")
def import_project(payload: ProjectImportRequest) -> dict:
    """!Import project, site, and job records."""
    project_id = payload.project.get("project_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required in payload.project")

    with LOCK:
        if project_id in PROJECTS:
            raise HTTPException(status_code=409, detail="project already exists")

        PROJECTS[project_id] = payload.project
        imported_sites = 0
        imported_jobs = 0
        for site in payload.sites:
            site_id = site.get("site_id")
            if not site_id:
                continue
            key = f"{project_id}:{site_id}"
            if key in SITES:
                continue
            SITES[key] = {**site, "project_id": project_id}
            imported_sites += 1

        for job in payload.jobs:
            job_id = job.get("job_id")
            if not job_id or job_id in JOBS:
                continue
            raw_payload = job.get("payload")
            safe_payload = raw_payload if isinstance(raw_payload, dict) else {}
            job_payload = {**safe_payload, "project_id": project_id}
            JOBS[job_id] = {**job, "payload": job_payload}
            imported_jobs += 1

        METRICS["projects_created_total"] += 1
        _persist_state()

    return {
        "project_id": project_id,
        "sites_imported": imported_sites,
        "jobs_imported": imported_jobs,
    }

@app.get("/v1/projects/{project_id}/export")
def export_project(project_id: str, include_jobs: bool = False) -> dict:
    """!Export project state and optional jobs."""
    with LOCK:
        if project_id not in PROJECTS:
            raise HTTPException(status_code=404, detail="project not found")
        sites = [s for s in SITES.values() if s["project_id"] == project_id]
        jobs = [j for j in JOBS.values() if j.get("payload", {}).get("project_id") == project_id]
        payload = {
            "project": PROJECTS[project_id],
            "sites": sites,
            "job_count": len(jobs),
        }
        if include_jobs:
            payload["jobs"] = jobs
        return payload

@app.post("/v1/projects/{project_id}/clone")
def clone_project(project_id: str, payload: ProjectCloneRequest) -> dict:
    """!Clone project metadata and sites."""
    with LOCK:
        if project_id not in PROJECTS:
            raise HTTPException(status_code=404, detail="project not found")
        if payload.new_project_id in PROJECTS:
            raise HTTPException(status_code=409, detail="new project_id already exists")

        PROJECTS[payload.new_project_id] = {"project_id": payload.new_project_id, "name": payload.new_name}
        copied_sites = 0
        for site in [s for s in SITES.values() if s["project_id"] == project_id]:
            key = f"{payload.new_project_id}:{site['site_id']}"
            SITES[key] = {**site, "project_id": payload.new_project_id}
            copied_sites += 1

        METRICS["projects_created_total"] += 1
        _persist_state()

    return {"project_id": payload.new_project_id, "sites_copied": copied_sites}

@app.delete("/v1/projects/{project_id}")
def delete_project(project_id: str, force: bool = False) -> dict:
    """!Delete a project and optional dependencies."""
    with LOCK:
        if project_id not in PROJECTS:
            raise HTTPException(status_code=404, detail="project not found")

        related_sites = [k for k, s in SITES.items() if s["project_id"] == project_id]
        related_jobs = [k for k, j in JOBS.items() if j.get("payload", {}).get("project_id") == project_id]

        if (related_sites or related_jobs) and not force:
            raise HTTPException(status_code=409, detail="project has dependent sites/jobs; use force=true")

        for k in related_sites:
            del SITES[k]
        for k in related_jobs:
            del JOBS[k]
        PROJECTS.pop(project_id, None)
        _persist_state()

    return {"project_id": project_id, "deleted": True, "sites_removed": len(related_sites), "jobs_removed": len(related_jobs)}

@app.post("/v1/projects/{project_id}/sites")
def create_project_site(project_id: str, payload: SiteCreate) -> dict:
    """!Create a site under a project."""
    with LOCK:
        if project_id not in PROJECTS:
            raise HTTPException(status_code=404, detail="project not found")
        key = f"{project_id}:{payload.site_id}"
        if key in SITES:
            raise HTTPException(status_code=409, detail="site already exists")
        SITES[key] = {
            "project_id": project_id,
            **payload.model_dump(),
        }
        METRICS["sites_created_total"] += 1
        _persist_state()
    return SITES[key]


@app.delete("/v1/projects/{project_id}/sites/{site_id}")
def delete_project_site(project_id: str, site_id: str, force: bool = False) -> dict:
    """!Delete a project site and optional dependent jobs."""
    key = f"{project_id}:{site_id}"
    with LOCK:
        if project_id not in PROJECTS:
            raise HTTPException(status_code=404, detail="project not found")
        if key not in SITES:
            raise HTTPException(status_code=404, detail="site not found")

        related_jobs = [k for k, j in JOBS.items() if j.get("payload", {}).get("project_id") == project_id and j.get("payload", {}).get("site_id") == site_id]

        if related_jobs and not force:
            raise HTTPException(status_code=409, detail="site has dependent jobs; use force=true")

        for k in related_jobs:
            del JOBS[k]
        del SITES[key]
        _persist_state()

    return {"project_id": project_id, "site_id": site_id, "deleted": True, "jobs_removed": len(related_jobs)}

@app.get("/v1/projects/{project_id}/sites")
def list_project_sites(project_id: str, limit: int = 100, offset: int = 0) -> dict:
    """!List paginated project sites."""
    if limit < 1 or offset < 0:
        raise HTTPException(status_code=400, detail="limit must be >= 1 and offset must be >= 0")
    with LOCK:
        if project_id not in PROJECTS:
            raise HTTPException(status_code=404, detail="project not found")
        sites = [s for s in SITES.values() if s["project_id"] == project_id]
    sliced = sites[offset: offset + limit]
    return {"project_id": project_id, "count": len(sites), "returned": len(sliced), "sites": sliced}


@app.get("/v1/projects/{project_id}/stats")
def get_project_stats(project_id: str) -> dict:
    """!Return aggregate project job/site stats."""
    with LOCK:
        if project_id not in PROJECTS:
            raise HTTPException(status_code=404, detail="project not found")

        project_jobs = [j for j in JOBS.values() if j.get("payload", {}).get("project_id") == project_id]
        by_status: dict[str, int] = {}
        for j in project_jobs:
            status = j.get("status", "unknown")
            by_status[status] = by_status.get(status, 0) + 1

        project_sites = [s for s in SITES.values() if s.get("project_id") == project_id]

    return {
        "project_id": project_id,
        "sites_total": len(project_sites),
        "jobs_total": len(project_jobs),
        "jobs_by_status": by_status,
    }


def _create_queued_job(payload: dict, submitted_at: str) -> str:
    """!Create an in-memory queued job and return its identifier."""
    job_id = f"sim_{uuid4().hex[:12]}"
    JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "submitted_at": submitted_at,
        "payload": payload,
        "events": [{"at": submitted_at, "status": "queued"}],
    }
    METRICS["jobs_created_total"] += 1
    _persist_state()
    _notify_external("job.queued", job_id, "queued", payload={"project_id": payload.get("project_id"), "site_id": payload.get("site_id")})
    return job_id

@app.post("/v1/projects/{project_id}/simulate")
def trigger_project_simulations(project_id: str) -> dict:
    """!Queue simulations for all project sites."""
    with LOCK:
        if project_id not in PROJECTS:
            raise HTTPException(status_code=404, detail="project not found")
        project_sites = [s for s in SITES.values() if s["project_id"] == project_id]

    created = []
    start = datetime.now(timezone.utc)
    end = start + timedelta(hours=1)
    now = start.isoformat()
    for site in project_sites:
        payload = {
            "project_id": project_id,
            "site_id": site["site_id"],
            "facility_type": site["facility_type"],
            "time_window": {"start_utc": start.isoformat(), "end_utc": end.isoformat()},
            "forcing_ref": {"dataset_id": "scheduled", "version": now},
            "parameters_ref": {"profile_id": "default"},
            "request_contract": "simulation_request.v1",
        }

        with LOCK:
            job_id = _create_queued_job(payload, now)

        if os.getenv("ASYNC_EXECUTION", "false").lower() == "true":
            task_id = enqueue_run({"job_id": job_id, "payload": payload})
            JOBS[job_id]["queue_task_id"] = task_id

        created.append(job_id)

    return {"project_id": project_id, "queued_jobs": len(created), "job_ids": created}


@app.post("/v1/projects/{project_id}/simulate/batch")
def trigger_project_simulations_batch(project_id: str, payload: BatchSimulateRequest) -> dict:
    """!Queue simulations for selected project sites with shared batch parameters."""
    with LOCK:
        if project_id not in PROJECTS:
            raise HTTPException(status_code=404, detail="project not found")
        sites = [s for s in SITES.values() if s["project_id"] == project_id]

    if payload.site_ids:
        selected = set(payload.site_ids)
        sites = [s for s in sites if s["site_id"] in selected]
    if not sites:
        raise HTTPException(status_code=400, detail="no matching project sites for batch request")
    if len(sites) > payload.max_jobs:
        raise HTTPException(status_code=400, detail=f"batch exceeds max_jobs={payload.max_jobs}")

    window_start = payload.time_window.start_utc if payload.time_window else datetime.now(timezone.utc)
    window_end = payload.time_window.end_utc if payload.time_window else window_start + timedelta(hours=1)
    submitted_at = datetime.now(timezone.utc).isoformat()

    created: list[str] = []
    for site in sites:
        job_payload = {
            "project_id": project_id,
            "site_id": site["site_id"],
            "facility_type": site["facility_type"],
            "time_window": {
                "start_utc": window_start.isoformat(),
                "end_utc": window_end.isoformat(),
            },
            "forcing_ref": payload.forcing_ref.model_dump(exclude_none=True),
            "parameters_ref": payload.parameters_ref.model_dump(exclude_none=True),
            "request_contract": "simulation_request.v1",
        }

        with LOCK:
            job_id = _create_queued_job(job_payload, submitted_at)

        if os.getenv("ASYNC_EXECUTION", "false").lower() == "true":
            task_id = enqueue_run({"job_id": job_id, "payload": job_payload})
            JOBS[job_id]["queue_task_id"] = task_id
        created.append(job_id)

    return {"project_id": project_id, "queued_jobs": len(created), "job_ids": created}

@app.post("/v1/simulations")
def create_simulation(
    payload: SimulationRequest,
    x_idempotency_key: str | None = Header(default=None),
) -> dict:
    """!Create and enqueue a simulation job."""
    now = datetime.now(timezone.utc).isoformat()

    with LOCK:
        if x_idempotency_key and x_idempotency_key in IDEMPOTENCY_INDEX:
            existing_job = IDEMPOTENCY_INDEX[x_idempotency_key]
            job = JOBS[existing_job]
            return {
                "job_id": existing_job,
                "status": job["status"],
                "submitted_at": job["submitted_at"],
                "idempotent_replay": True,
            }

        if payload.project_id not in PROJECTS:
            raise HTTPException(status_code=404, detail="unknown project_id")
        site_key = f"{payload.project_id}:{payload.site_id}"
        if site_key not in SITES:
            raise HTTPException(status_code=404, detail="unknown site_id for project")
        if SITES[site_key]["facility_type"] != payload.facility_type:
            raise HTTPException(status_code=400, detail="facility_type mismatch for site")

        job_id = f"sim_{uuid4().hex[:12]}"
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "submitted_at": now,
            "payload": payload.model_dump(mode="json"),
            "events": [{"at": now, "status": "queued"}],
        }
        if x_idempotency_key:
            IDEMPOTENCY_INDEX[x_idempotency_key] = job_id
        METRICS["jobs_created_total"] += 1
        _persist_state()

    if os.getenv("ASYNC_EXECUTION", "false").lower() == "true":
        task_id = enqueue_run({"job_id": job_id, "payload": JOBS[job_id]["payload"]})
        JOBS[job_id]["queue_task_id"] = task_id

    return {"job_id": job_id, "status": "queued", "submitted_at": now, "queue_task_id": JOBS[job_id].get("queue_task_id")}


@app.post("/v1/simulations/{job_id}/start")
def mark_started(job_id: str) -> dict:
    """!Mark a job as running."""
    now = datetime.now(timezone.utc).isoformat()
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        job["status"] = "running"
        job["started_at"] = now
        job["events"].append({"at": now, "status": "running"})
        _persist_state()
    _notify_external("job.started", job_id, "running")
    return {"job_id": job_id, "status": "running"}


@app.post("/v1/simulations/{job_id}/complete")
def mark_completed(job_id: str, result: CompletionPayload) -> dict:
    """!Mark a job as completed with result payload."""
    now = datetime.now(timezone.utc).isoformat()
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        job["status"] = "completed"
        job["finished_at"] = now
        job["events"].append({"at": now, "status": "completed"})
        job["result"] = {
            "job_id": job_id,
            "status": "completed",
            "result_contract": "simulation_result.v1",
            "generated_at_utc": now,
            "adapter": {
                "engine": "manual",
                "mock": False,
                "mock_mode": False,
                "raw": {},
            },
            "metrics": result.model_dump(),
        }
        METRICS["jobs_completed_total"] += 1
        _persist_state()
    _notify_external("job.completed", job_id, "completed", payload={"result_contract": "simulation_result.v1"})
    return {"job_id": job_id, "status": "completed"}


@app.post("/v1/simulations/{job_id}/cancel")
def cancel_simulation(job_id: str, reason: str | None = None) -> dict:
    """!Cancel a job and record cancellation reason."""
    now = datetime.now(timezone.utc).isoformat()
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        if job.get("status") in {"completed", "failed"}:
            raise HTTPException(status_code=409, detail="job already finalized")
        job["status"] = "cancelled"
        job["finished_at"] = now
        job["cancel_reason"] = reason or "cancelled by user"
        job["events"].append({"at": now, "status": "cancelled"})
        METRICS["jobs_cancelled_total"] += 1
        _persist_state()
    _notify_external("job.cancelled", job_id, "cancelled", payload={"reason": reason or "cancelled by user"})
    return {"job_id": job_id, "status": "cancelled"}

@app.post("/v1/simulations/{job_id}/fail")
def mark_failed(job_id: str, error_message: str | None = None) -> dict:
    """!Mark a job as failed with error details."""
    now = datetime.now(timezone.utc).isoformat()
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        job["status"] = "failed"
        job["finished_at"] = now
        job["error_message"] = error_message or "unknown error"
        job["events"].append({"at": now, "status": "failed"})
        METRICS["jobs_failed_total"] += 1
        _persist_state()
    _notify_external("job.failed", job_id, "failed", payload={"error_message": error_message or "unknown error"})
    return {"job_id": job_id, "status": "failed"}

@app.post("/v1/internal/simulations/{job_id}/result")
def post_worker_result(job_id: str, payload: WorkerResultPayload, x_internal_token: str | None = Header(default=None)) -> dict:
    """!Ingest worker callback result for a job."""
    configured = os.getenv("INTERNAL_API_TOKEN")
    if configured and x_internal_token != configured:
        raise HTTPException(status_code=403, detail="forbidden")

    now = datetime.now(timezone.utc).isoformat()
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        job["status"] = payload.status
        job["finished_at"] = now
        job["events"].append({"at": now, "status": payload.status})
        job["result"] = {
            "job_id": job_id,
            "status": payload.status,
            "result_contract": payload.result_contract,
            "metrics": payload.metrics.model_dump(),
            "adapter": payload.adapter.model_dump(),
            "generated_at_utc": payload.generated_at_utc.isoformat() if payload.generated_at_utc else now,
        }
        if payload.status == "completed":
            METRICS["jobs_completed_total"] += 1
        elif payload.status == "failed":
            METRICS["jobs_failed_total"] += 1
        _persist_state()
    _notify_external(
        "job.worker_result",
        job_id,
        payload.status,
        payload={"result_contract": payload.result_contract, "engine": payload.adapter.engine},
    )
    return {"job_id": job_id, "status": payload.status}

@app.get("/v1/projects/{project_id}/simulations")
def list_project_simulations(project_id: str, status: str | None = None, limit: int = 100, offset: int = 0) -> dict:
    """!List paginated project simulations."""
    if limit < 1 or offset < 0:
        raise HTTPException(status_code=400, detail="limit must be >= 1 and offset must be >= 0")
    with LOCK:
        if project_id not in PROJECTS:
            raise HTTPException(status_code=404, detail="project not found")
        jobs = [
            {
                "job_id": job["job_id"],
                "status": job["status"],
                "project_id": job["payload"]["project_id"],
                "site_id": job["payload"]["site_id"],
                "submitted_at": job["submitted_at"],
            }
            for job in JOBS.values()
            if job["payload"]["project_id"] == project_id
        ]
    if status is not None:
        jobs = [j for j in jobs if j["status"] == status]
    sliced = jobs[offset: offset + limit]
    return {"project_id": project_id, "count": len(jobs), "returned": len(sliced), "jobs": sliced}


@app.get("/v1/projects/{project_id}/simulations/summary")
def get_project_simulations_summary(project_id: str, status: str | None = None) -> dict:
    """!Return aggregate simulation summary for dashboard usage."""
    with LOCK:
        if project_id not in PROJECTS:
            raise HTTPException(status_code=404, detail="project not found")

        project_jobs = [
            job for job in JOBS.values() if job.get("payload", {}).get("project_id") == project_id
        ]
        if status is not None:
            project_jobs = [job for job in project_jobs if job.get("status") == status]

    by_status: dict[str, int] = {}
    by_site: dict[str, dict[str, int]] = {}
    for job in project_jobs:
        job_status = job.get("status", "unknown")
        site_id = job.get("payload", {}).get("site_id", "unknown")
        by_status[job_status] = by_status.get(job_status, 0) + 1
        if site_id not in by_site:
            by_site[site_id] = {"total": 0}
        by_site[site_id]["total"] += 1
        by_site[site_id][job_status] = by_site[site_id].get(job_status, 0) + 1

    total_jobs = len(project_jobs)
    completed_jobs = by_status.get("completed", 0)
    completion_rate = (completed_jobs / total_jobs) if total_jobs else 0.0

    return {
        "project_id": project_id,
        "filtered_status": status,
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "completion_rate": completion_rate,
        "by_status": by_status,
        "by_site": by_site,
    }

@app.get("/v1/simulations/{job_id}")
def get_simulation(job_id: str) -> dict:
    """!Get job lifecycle metadata."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "submitted_at": job["submitted_at"],
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "events": job.get("events", []),
        "retry_of": job.get("retry_of"),
    }


@app.post("/v1/simulations/{job_id}/retry")
def retry_simulation(job_id: str, payload: RetrySimulationRequest) -> dict:
    """!Retry an existing simulation by re-queueing a new child job."""
    with LOCK:
        original = JOBS.get(job_id)
        if not original:
            raise HTTPException(status_code=404, detail="job not found")

        original_status = original.get("status")
        if original_status in {"queued", "running"} and not payload.force:
            raise HTTPException(
                status_code=409,
                detail="job is still active; set force=true to retry anyway",
            )

        now = datetime.now(timezone.utc).isoformat()
        retry_payload = dict(original.get("payload", {}))
        new_job_id = _create_queued_job(retry_payload, now)
        JOBS[new_job_id]["retry_of"] = job_id
        original.setdefault("events", []).append({"at": now, "status": "retried", "new_job_id": new_job_id})
        _persist_state()

    _notify_external(
        "job.retried",
        new_job_id,
        "queued",
        payload={"retry_of": job_id, "original_status": original_status},
    )
    return {
        "job_id": new_job_id,
        "status": "queued",
        "retry_of": job_id,
        "original_status": original_status,
    }


@app.get("/v1/simulations/{job_id}/events")
def get_simulation_events(job_id: str) -> dict:
    """!Get job event history."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    events = job.get("events", [])
    return {"job_id": job_id, "count": len(events), "events": events}


@app.get("/v1/simulations/{job_id}/events/poll")
def poll_simulation_events(job_id: str, after_index: int = 0, timeout_s: float = 15.0) -> dict:
    """!Long-poll for new simulation events after a known index."""
    if after_index < 0:
        raise HTTPException(status_code=400, detail="after_index must be >= 0")
    if timeout_s < 0 or timeout_s > 30:
        raise HTTPException(status_code=400, detail="timeout_s must be between 0 and 30 seconds")

    deadline = time.monotonic() + timeout_s
    final_states = {"completed", "failed", "cancelled"}

    while True:
        with LOCK:
            job = JOBS.get(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="job not found")
            events = job.get("events", [])
            status = job.get("status", "unknown")
            next_index = len(events)

            if after_index < next_index:
                return {
                    "job_id": job_id,
                    "status": status,
                    "from_index": after_index,
                    "next_index": next_index,
                    "count": next_index - after_index,
                    "events": events[after_index:],
                    "timed_out": False,
                }

            if status in final_states:
                return {
                    "job_id": job_id,
                    "status": status,
                    "from_index": after_index,
                    "next_index": next_index,
                    "count": 0,
                    "events": [],
                    "timed_out": False,
                }

        if time.monotonic() >= deadline:
            return {
                "job_id": job_id,
                "status": status,
                "from_index": after_index,
                "next_index": next_index,
                "count": 0,
                "events": [],
                "timed_out": True,
            }

        time.sleep(0.25)

@app.get("/v1/simulations/{job_id}/results")
def get_simulation_results(job_id: str) -> dict:
    """!Get job result payload."""
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job["status"] != "completed":
        return {
            "job_id": job_id,
            "status": job["status"],
            "message": "results not ready",
        }
    return job["result"]
