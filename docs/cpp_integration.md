# C++ Integration Guide (starter)

This scaffold is implemented in Python, but the orchestration contract is HTTP/JSON-based and can be consumed from C++ or any other language.

## Core interoperability points
- Submit jobs via `POST /v1/simulations`.
- Receive worker results via `POST /v1/internal/simulations/{job_id}/result`.
- Subscribe to lifecycle events with outbound webhooks (`OUTBOUND_WEBHOOK_URL`) or polling (`GET /v1/simulations/{job_id}/events/poll`).
- Use idempotency (`X-Idempotency-Key`) for safe retries on create/batch operations.

## Suggested C++ implementation tasks
1. Create a small C++ client wrapper for submit/status/result/event APIs.
2. Add JSON model structs aligned to the repository schemas (`simulation_request.v1`, `simulation_result.v1`).
3. Add conformance tests that replay the same API scenarios as Python tests.
4. Add webhook signature/auth validation if required by your deployment.

## Notes
- Keep API payload formats versioned and backward-compatible.
- Prefer contract tests over implementation-coupled tests to preserve language freedom.
