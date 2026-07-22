# ADR: Scheduler Architecture

## Question

Should scheduled checks run inside the FastAPI process, or in a separate worker service?

The scheduler needs to:

1. Read enabled targets from Postgres.
2. Check each target over HTTP.
3. Cache useful status data in Redis.
4. Persist results to Postgres.

## Option A: In-process scheduler — chosen for Phase 1

`AsyncIOScheduler` starts and stops through FastAPI's lifespan context manager. The API and scheduler run in the same Uvicorn process and container.

**Benefits**

- Simple to implement and deploy.
- Requires no queue, distributed lock, or worker coordination.
- Uses the existing Dockerfile and Compose service.
- Proves the complete check-schedule-persist flow with minimal infrastructure.

**Costs**

- The API and scheduler share the same failure domain. If the app process stops, scheduled checks also stop.
- Requests and scheduled jobs share CPU, memory, and executor capacity.
- The scheduler cannot scale independently from the API.
- Running multiple API replicas would create multiple schedulers unless coordination was added.

Overlap controls such as `max_instances` and `coalesce` help prevent slow jobs from creating a backlog. Results are persisted to Postgres as soon as a check completes, before any Redis write, so a process crash may lose an in-progress check, but previously stored history remains safe.

## Option B: Separate worker service — out of scope for Phase 1

A separate container would run the scheduler independently, connecting to Postgres and Redis through the Compose network.

**Benefits**

- The API and workers can scale independently.
- Worker failures do not directly stop the API.
- Each service can be tested and observed separately.

**Costs**

- Multiple workers require coordination to avoid duplicate checks: a job queue, target partitioning, or a Redis-based lock (`SET key value NX EX ttl` to claim a target for the duration of its check).
- Introduces additional services, deployment work, tests, and failure modes.
- Solves a scaling problem the current project does not have.

This is the architecture used by systems such as Celery, RQ, and ARQ, but those tools are outside the current phase.

## Decision

Use the in-process scheduler for Phase 1.

The current goal is to prove the autonomous pipeline works end to end, not to build a horizontally scalable worker system. The in-process design proves target loading, HTTP checks, Redis updates, and Postgres persistence without adding unnecessary coordination infrastructure.

A separate worker becomes the natural next step if target volume, check frequency, or reliability requirements exceed what one application process can handle.


