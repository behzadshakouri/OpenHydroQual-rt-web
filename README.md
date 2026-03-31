# openhydroqual-rt-web (starter scaffold)

Reference scaffold for a real-time orchestration repo around OpenHydroQual/OHQuery.

## Current status (March 30, 2026)
This repository is currently a **starter orchestration scaffold**:
- API and worker stubs are in place.
- Core request/result data contracts are defined.
- Queueing, callback, and project/site lifecycle endpoints exist.
- Persistence and execution are still scaffold-level (in-memory/file-state + adapter stubs).

If your goal is production web usage for OpenHydroQual
([ArashMassoudieh/OpenHydroQual](https://github.com/ArashMassoudieh/OpenHydroQual)),
the next sections describe what to build next.

## What to build next (recommended sequence)
1. **Execution integration (highest priority)**
   - Replace stubbed execution with a robust OpenHydroQual runtime contract.
   - Standardize input artifact generation (`.ohq`/script payloads) and output parsing.
   - Add deterministic error mapping for engine failures/timeouts.
2. **Persistence hardening**
   - Move API state from in-memory/file mode to PostgreSQL-backed repositories.
   - Add migration-backed models for projects, sites, runs, events, and result metrics.
3. **Job orchestration robustness**
   - Add retries/backoff, dead-letter handling, and cancellation semantics in worker flow.
   - Add idempotent re-delivery protections for worker callback endpoint.
4. **Web product surface**
   - Add authn/authz, tenant/project isolation, and API tokens.
   - Build UI/API for run submission, run history, logs, and result visualization.
5. **Observability + operability**
   - Expand metrics beyond counters (latency/error-rate/queue depth).
   - Add structured logging, tracing, and run/audit correlation IDs.
6. **Contract + integration tests**
   - Add full integration tests against real Redis/Postgres and a mocked OpenHydroQual process.
   - Add compatibility tests for data-contract versions across API/worker boundaries.

## Included
- FastAPI app with:
  - `POST /v1/projects`
  - `POST /v1/projects/{project_id}/sites`
  - `GET /v1/projects/{project_id}/export` (supports `include_jobs=true`)
  - `POST /v1/projects/import` (supports `jobs` in payload)
  - `POST /v1/projects/{project_id}/clone`
  - `DELETE /v1/projects/{project_id}` (supports `force=true`)
  - `DELETE /v1/projects/{project_id}/sites/{site_id}` (supports `force=true`)
  - `GET /v1/projects/{project_id}/sites` (supports `limit`, `offset`)
  - `POST /v1/simulations`
  - `POST /v1/projects/{project_id}/simulate` (queue all project sites)
  - `POST /v1/projects/{project_id}/simulate/batch` (queue selected project sites with shared params)
  - `GET /v1/projects/{project_id}/stats`
  - `GET /v1/projects/{project_id}/simulations` (supports `status`, `limit`, `offset`)
  - `GET /v1/projects/{project_id}/simulations/summary` (aggregated status/site counts for dashboards)
  - `GET /v1/projects/{project_id}/sites/{site_id}/simulations/summary` (site-specific status summary)
  - `GET /v1/projects/{project_id}/simulations/timeline/summary` (avg/p95 timeline metrics)
  - `GET /v1/projects/{project_id}/simulations/failures` (failed/cancelled records with retry hints)
  - `GET /v1/projects/{project_id}/simulations/queue` (queued/running jobs with stale indicators)
  - `POST /v1/projects/{project_id}/simulations/retry-failed` (bulk retry by status with limit)
  - `POST /v1/projects/{project_id}/simulations/requeue-stale` (dry-run or requeue stale queued/running jobs)
  - `POST /v1/projects/{project_id}/simulations/prune` (dry-run or delete historical jobs by status/date)
  - `POST /v1/simulations/{job_id}/start`
  - `POST /v1/simulations/{job_id}/complete`
  - `POST /v1/simulations/{job_id}/retry` (re-queue a child job from an existing run)
  - `POST /v1/simulations/{job_id}/cancel`
  - `POST /v1/simulations/{job_id}/fail`
  - `GET /v1/simulations/{job_id}`
  - `GET /v1/simulations/{job_id}/lineage` (retry ancestry and child jobs)
  - `GET /v1/simulations/{job_id}/timeline` (queue/run/total duration breakdown)
  - `GET /v1/simulations/{job_id}/events`
  - `GET /v1/simulations/{job_id}/events/poll` (long-poll updates after known event index)
  - `GET /v1/simulations/{job_id}/results`
  - `POST /v1/internal/simulations/{job_id}/result` (worker callback)
  - `GET /metrics` (Prometheus-style counters)
  - `GET /v1/system/idempotency` (operation idempotency cache health/stats)
  - `GET /v1/system/webhooks` (recent outbound webhook delivery audit records)
- `/metrics` includes outbound webhook delivery counters (`webhook_notify_success_total`, `webhook_notify_failure_total`)
- Idempotency support via `X-Idempotency-Key` header on create endpoint
- `POST /v1/projects/{project_id}/simulate/batch` also supports `X-Idempotency-Key` to replay prior batch responses.
- `POST /v1/simulations` validates project/site existence and facility type match
- Celery worker stub for queued simulation runs
- JSON Schemas for request/result contracts (`simulation_request.v1`, `simulation_result.v1`)
- SQL migration starter for `site`, `forcing_series`, `simulation_run`
- Docker Compose stack for API + worker + Redis + Postgres

## Quick start
```bash
cd openhydroqual-rt-web
make install
.venv/bin/uvicorn apps.api.main:app --reload --port 8000
```

In a second terminal:
```bash
cd openhydroqual-rt-web
make install
.venv/bin/celery -A apps.worker.tasks worker --loglevel=info
```

## Local API smoke flow
```bash
# create project + site
curl -s -X POST http://localhost:8000/v1/projects \
  -H 'Content-Type: application/json' \
  -d '{"project_id":"la-drywell-pilot","name":"LA Drywell Pilot"}'

curl -s -X POST http://localhost:8000/v1/projects/la-drywell-pilot/sites \
  -H 'Content-Type: application/json' \
  -d '{"site_id":"la-00123","facility_type":"drywell","latitude":34.05,"longitude":-118.24,"metadata":{"county":"LA"}}'

# create
curl -s -X POST http://localhost:8000/v1/simulations \
  -H 'Content-Type: application/json' \
  -H 'X-Idempotency-Key: demo-1' \
  -d '{
    "project_id":"la-drywell-pilot",
    "site_id":"la-00123",
    "facility_type":"drywell",
    "time_window":{"start_utc":"2026-03-26T00:00:00Z","end_utc":"2026-03-27T00:00:00Z"},
    "forcing_ref":{"dataset_id":"noaa-hourly","version":"2026-03-26T00:15:00Z"},
    "parameters_ref":{"profile_id":"drywell-default-v1"},
    "request_contract":"simulation_request.v1"
  }'

# trigger queued runs for all sites in a project
curl -s -X POST http://localhost:8000/v1/projects/la-drywell-pilot/simulate

# mark started + completed
curl -s -X POST http://localhost:8000/v1/simulations/<JOB_ID>/start
curl -s -X POST http://localhost:8000/v1/simulations/<JOB_ID>/complete \
  -H 'Content-Type: application/json' \
  -d '{"peak_depth_m":0.12,"infiltrated_volume_m3":8.5,"overflow":false}'
```

## AWS deployment notes
- Use **RDS PostgreSQL** for relational storage.
- Use **ElastiCache Redis** (or Amazon MQ/SQS adapter if preferred) for broker/backend.
- Run API/worker containers on **ECS Fargate** (or EKS) with private networking.
- Expose API via **ALB** + HTTPS; keep OHQuery service internal behind private ALB or service discovery.
- Set environment variables from `.env.example` using AWS Secrets Manager / SSM Parameter Store.

Minimum environment variables in AWS:
- `ASYNC_EXECUTION=true`
- `BROKER_URL` (ElastiCache endpoint)
- `RESULT_BACKEND` (ElastiCache endpoint)
- `OHQUERY_BASE_URL` (internal OHQuery service URL)

### Send/receive flow with AWS services
- **Receive from AWS worker:** API accepts worker callbacks at `POST /v1/internal/simulations/{job_id}/result`.
- **Send to AWS/web clients:** set `OUTBOUND_WEBHOOK_URL` to push job lifecycle events (`queued`, `started`, `completed`, `failed`, etc.) to an AWS endpoint (API Gateway, Lambda URL, EventBridge Pipe target, or your own webhook service).
- **Receive in web clients:** call `GET /v1/simulations/{job_id}/events/poll?after_index=<n>&timeout_s=15` for long-poll incremental updates.
- Optional write protection: set `WRITE_API_TOKEN` and pass `X-Api-Token` on mutating endpoints.
- Batch idempotency cache TTL can be tuned via `OPERATION_IDEMPOTENCY_TTL_SECONDS` (default 86400).
- Outbound webhook audit retention can be tuned via `WEBHOOK_AUDIT_MAX` (default 200 records).
- Optional auth header for outbound events: set `OUTBOUND_WEBHOOK_TOKEN` (sent as `Authorization: Bearer <token>`).

Example (Lambda Function URL or API Gateway webhook target):
```bash
export OUTBOUND_WEBHOOK_URL="https://<aws-endpoint>/job-events"
export OUTBOUND_WEBHOOK_TOKEN="<shared-secret-token>"
```


## OHQuery integration mode
- Default local mode uses `MOCK_OHQUERY=true` (no external engine call).
- Set `MOCK_OHQUERY=false` and `OHQUERY_BASE_URL=http://<ohquery-host>:8080` to call real OHQuery `POST /calculate`.
- For direct engine execution, set `OPENHYDROQUAL_CMD` (e.g., `/opt/openhydroqual/bin/OpenHydroQualCLI`) and pass `script_path` (or `ohq_script_path`) in simulation payload parameters.


## Testing
```bash
cd openhydroqual-rt-web
make install
make test-fast   # quick worker+adapter feedback loop
make test
```

A GitHub Actions workflow is included at `.github/workflows/openhydroqual-rt-web-ci.yml` to run scaffold tests automatically.


## Optional local state persistence
- By default API state is in-memory only.
- Set `ENABLE_FILE_STATE=true` to persist projects/sites/jobs in `STATE_FILE` (JSON file) across restarts.


## Worker callback endpoint
Workers can push normalized results back to API using `POST /v1/internal/simulations/{job_id}/result`.
Set `INTERNAL_API_TOKEN` and pass it in `X-Internal-Token` for simple protection.
Accepted callback statuses are `completed` and `failed`.
Lifecycle transitions are guarded; finalized jobs (`completed`/`failed`/`cancelled`) cannot transition to a different status.

Example callback payload:

```json
{
  "status": "completed",
  "result_contract": "simulation_result.v1",
  "generated_at_utc": "2026-03-27T00:00:00+00:00",
  "adapter": {
    "engine": "OHQuery",
    "mock": true,
    "mock_mode": true,
    "raw": { "mock": true }
  },
  "metrics": {
    "peak_depth_m": 0.11,
    "infiltrated_volume_m3": 7.9,
    "overflow": false
  }
}
```
