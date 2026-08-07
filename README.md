# synthetic-uptime-monitor

## What is a Synthetic Uptime Monitor

A synthetic uptime monitor is a service which generates periodic HTTP requests to target services. It then records observations on whether the service could be reached and how the service responded to our request. These observations are used to measure the services availability and its performance over time. 

### What is Uptime?

*Uptime* is a measure of *availability*, generally measured as a percentage over some base unit of time. If our base unit is 1 day with 24 hours, and our service, say a website is down for 48 minutes, then we'd have about `23 hours, 12 minutes` which comes to `(23 + 12/60) / 24 = 96.67% uptime`. Or if it is down for 4 hours out of an entire month then `(716/720) * 100 = 99.44% uptime` 


### What is an Uptime Monitor?

This is a service/application whose job is to determine if a service is up/available, It checks repeatedly and from these checks it can determine the following
- uptime percentage
- outage duration
- average latency
- failure count

> Note that an uptime monitor records observations and from that determines the uptime (and associated data)


### What does the Synthetic Part Refer to?

This refers to *synthetically* generating traffic, that is requests that imitate real users. For example the monitor could do something like `GET https://google.com/health` 


### Why Even Do This?

Since we'd like to know when a application / service is down we could just wait until a user experiences a failure but that would degrade user experience, so instead by generating synthetic traffic we can more readily check when our services are down. If a website is down during low traffic and we used only user input to determine this then it could take hours before a real user notices and reports the issue. By using synthetic monitoring we can know about problems before they reach our users.


### So Really What is it Doing?

Every few seconds send an HTTP request, measure the status code, the latency, the error class (if there was an error) and the time of the request, store this information, and repeat.


## How the Scheduler Works

The scheduler is built on APScheduler's `AsyncIOScheduler`, started and
stopped through FastAPI's `lifespan` context manager so its lifecycle
matches the app process. On startup, two recurring jobs are registered:
`target_scanner`, which manages all the per-target check jobs, and the
per-target `check-target-{id}` jobs it creates.

### `target_scanner`

Runs on a fixed interval (currently 20s, with `max_instances=1` to prevent
overlapping scans) and reconciles two sets:

- **Expected targets** — queried fresh from Postgres each run: all
  `EndpointTarget` rows with `enabled = true`.
- **Current jobs** — read from the live scheduler via `scheduler.get_jobs()`,
  filtered to only jobs whose id starts with `check-target-` (this excludes
  the scanner's own job from the comparison).

The two sets are diffed by target id:

- Expected but not current → `scheduler.add_job(perform_check, ...)` is
  called, registering a new job with id `check-target-{id}` on an interval
  matching that target's `interval_seconds`, with `max_instances=1` on
  **this per-target job** to prevent overlapping runs of the same check.
- Current but not expected → `scheduler.remove_job(...)` is called, removing
  the job for a target that's been disabled since the last scan.

This means enabling or disabling a target doesn't require an app
restart. The next `target_scanner` run (within 20s) picks up the change.

### `perform_check`

Each per-target job calls `perform_check(target_id)`, which:

1. Re-queries the target's row from Postgres by id, rather than trusting
   whatever config was passed at scheduling time. This avoids acting on
   stale data if the target was edited between the scanner's last scan and
   this job firing.
2. Raises `TargetNotFoundError` if no row exists for that id at all — the
   only exception path in this function, reserved for a genuinely missing
   target (e.g. deleted but its job wasn't cleaned up yet).
3. If the row exists but `enabled` is `False`, does nothing and returns.
   This is not an error: it means the target was disabled after the
   scanner's last scan, so its job hasn't been removed yet. No HTTP check
   runs and nothing is recorded. The next `target_scanner` pass will remove
   this job so it stops firing.
4. If the row exists and `enabled` is `True`, calls `complete_check(url,
   target_id, timeout_seconds)` to perform the HTTP request and gather
   status code, latency, and error classification, then passes the result
   to `record_check_result`, which persists it as a new `CheckResult` row
   in Postgres and, when caching is enabled, writes a last-known-status
   entry to Redis with a TTL.

### Known inefficiency (noted, not yet addressed)

`target_scanner` already queries target data while building the expected
set, but `perform_check` re-queries the same row again when its job fires.
This is intentional (see point 1 above — it avoids scheduling against stale
config), but it does mean the data is fetched twice: once for the scanner's
diff and once for the actual check. Not a correctness problem, just a note
for anyone optimizing query load later.

## Database Schema

### `EndpointTarget`

Stores the configuration details for every endpoint we want to monitor.

| **Field**                | **Purpose**                                                                                                                                                              |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                       | Identifier for the endpoint.                                                                                                                                            |
| `url`                      | The endpoint that will receive HTTP requests.                                                                                                                           |
| `method`                   | The HTTP method (`GET`, `POST`, etc.) used when checking the endpoint.                                                                                                  |
| `interval_seconds`         | How often the endpoint should be checked.                                                                                                                               |
| `timeout_seconds`          | How long to wait before considering the request to have timed out.                                                                                                     |
| `failure_threshold`        | Number of consecutive failed checks before the endpoint is considered down.                                                                                            |
| `expected_status`          | The HTTP status code considered to represent a healthy response. This allows endpoints that intentionally return codes other than `200` to still be considered healthy. |
| `current_failed_checks`    | Running count of consecutive errors and failures (a request that never got a response, or one that returned an unexpected status). Resets to `0` on any check that reaches the endpoint and receives the `expected_status`. |
| `enabled`                  | Indicates whether this endpoint should currently be monitored.                                                                                                          |
| `created_at`               | When the endpoint configuration was created.                                                                                                                            |
| `updated_at`               | When the endpoint configuration was last modified.                                                                                                                      |

### `CheckResult`

Stores the outcome of every single health check performed by the monitor, with each row being its own observation.

| **Field**     | **Purpose**                                                                                                                                                             |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`           | Unique identifier for the observation.                                                                                                                                 |
| `target_id`    | Foreign key linking the result back to the `EndpointTarget` that generated it.                                                                                         |
| `status_code`  | The HTTP status code returned by the endpoint, if a response was received.                                                                                             |
| `latency_ms`   | Time between sending the request and receiving the response, measured in milliseconds.                                                                                |
| `error_class`  | The name of the exception raised when the request could not be completed at all (for example, a timeout or DNS resolution failure). `NULL` whenever a response was received, whether or not that response matched `expected_status`. See "Error vs Failure" below for the distinction. |
| `checked_at`   | Timestamp indicating when the check was performed.                                                                                                                     |

#### Error vs Failure

We decided to draw a distinction between errors and failures.

`complete_check()` makes the HTTP request and returns the raw outcome, it does not judge whether that outcome is good or bad. An inability to reach the endpoint at all (timeout, connection refused, DNS failure, etc.) is what we call an **error**. In this case `error_class` is set to the name of the `httpx` exception raised (`type(e).__name__`), and `status_code` stays `None`, since no response was ever received.

Reaching the endpoint but getting back the wrong status code, for example a target expects `404` but the server returns `200`, is not an error. We call this a **failure**. `error_class` stays `None` here, because the request itself succeeded, we don't want to overload what `error_class` means by using it for both "the request never completed" and "the request completed with an unwanted result." A status mismatch can be found by joining `check_result` against `endpoint_target` and comparing `status_code` to `expected_status`. This join is left to whatever consumes the data later, an observability tool, a dashboard, or a human, rather than being pre-computed and stored.

The `current_failed_checks` field on `endpoint_target` is where errors and failures meet. It increments on either an error or a failure, and resets to `0` on a genuine success. This keeps the counter simple: it answers "is this target currently unhealthy," not "why." That does mean the counter alone can't tell you whether a target is unreachable or just returning the wrong status, only that something has been wrong for N checks in a row. Anyone who needs the distinction has to look at the underlying `check_result` rows (`status_code` and `error_class`) to see the actual cause. This is a deliberate simplicity trade-off, not an oversight, and it's documented here so it isn't a surprise later.

## Current Status

- Week 0
  - `/health` and `/ready` endpoints setup. Project structure setup. Pytest tests for these endpoints setup.
  - Dockerfile and docker-compose.yml written. Full stack (app, db, redis) verified with `docker compose up --build`.
- Week 1
  - SQLAlchemy models (`EndpointTarget`, `CheckResult`) and first Alembic migration written and applied.
  - `/ready` wired to actually check Postgres via `SELECT 1`.
  - Full CRUD on `/targets` implemented (create, list, get, update, disable).
  - Check-result persistence and `GET /targets/{id}/results` implemented.
  - Redis wired in as last-status cache with TTL, `/ready` checks Redis too.
  - Test suite expanded to cover CRUD, persistence, and dependency checks. Test database uses savepoint-based transaction rollback fixtures so each test runs against a clean, consistent state without needing to rebuild the database between runs.
  - Postgres-down and Redis-down failure drills run and documented, both recover cleanly with no data loss.
- Week 2
  - `app/checker.py` implemented: `complete_check` hits a target via `httpx`, captures status code, latency, error class, timestamp.
  - APScheduler wired through `lifespan`. `target_scanner` reconciles DB targets against live jobs; `perform_check` runs checks and persists results on interval. `max_instances=1` guards against overlap.
  - Verified running autonomously on local machine and y540-server, including disable-via-PATCH correctly stopping checks.
  - Error classification split (`ConnectTimeout`, `ConnectError`, catch-all) in `checker.py`.
  - `current_failed_checks` counter added on `EndpointTarget`, increments/resets with check outcome.
  - DB-level `CHECK` constraint (`timeout_seconds < interval_seconds`) added via migration.
  - Structured JSON logging via `structlog`, correlation ID middleware, `execution_id` on scheduled checks.
  - Test suite expanded to 29 tests covering scanner, checker, and scheduler logic. Passing on both local machine and y540-server.



## Architecture Vision
- A synthetic uptime monitor which sends HTTP requests to a list of some target URLs then records the response time and status codes, which will be stored in a PostgreSQL database. Redis is used to hold short lived operational states, for example the last known target status. 
The metrics will be exposed via Prometheus, visualized using Grafana, and finally routed using Alertmanager

## Architecture Diagram

```mermaid
flowchart TB
    Client[Client] -->|HTTP: POST/GET/PATCH /targets| API[FastAPI App]

    subgraph App[FastAPI App Process]
        API
        Scheduler[APScheduler]
        Scanner[target_scanner]
        Checker[perform_check]
        Scheduler --> Scanner
        Scanner -->|adds/removes jobs| Checker
    end

    API -->|CRUD| PG[(PostgreSQL)]
    Checker -->|HTTP request| Target[Monitored Target URL]
    Checker -->|persist CheckResult,<br/>update current_failed_checks| PG
    Checker -->|cache last status, TTL| Redis[(Redis)]
    Checker -->|increment/observe| Metrics[In-process Metrics<br/>checks_total, check_latency_seconds]

    Metrics -->|exposed via| MetricsEP["/metrics endpoint"]
    Prom[Prometheus] -->|scrapes every 15s| MetricsEP
    Prom -->|evaluates rules| Rules[alerts.yml]
    Rules -->|PENDING then FIRING| Prom
    Prom -->|firing alerts| AM[Alertmanager]
    AM -->|webhook| Notify[ALERT_WEBHOOK_URL]

    Grafana[Grafana] -->|PromQL queries| Prom
    Client -->|views dashboards| Grafana
```

## Components and Why Each Exists

### FastAPI
I wanted a pure JSON API. Django is "batteries-included" (templates, admin
dashboard, ORM) for a full web application, none of which this project
needs. FastAPI turns incoming requests into Python function calls and
serializes the return value back into a response, using type hints to
validate request/response shapes at the boundary, which is exactly the
surface area a monitoring API needs and nothing more.

### PostgreSQL
Chosen for persistent storage of targets and their check history. Relational
storage fits the data naturally: `EndpointTarget` and `CheckResult` are in a
real foreign-key relationship, and I wanted the ACID guarantees that come
with it. It's also the database I have the most prior experience with.

### Redis
Redis is **not** the source of truth, Postgres is. Redis holds short-lived
operational state (last-known status per target, cached with a TTL) that is
safe to lose and rebuild: if Redis goes down, the app degrades (freshness of
cached status), it does not lose data. Historical results always live in
Postgres regardless of Redis's availability. That separation is deliberate:
a temporary cache outage must never become permanent data loss. 


### Prometheus + Grafana + Alertmanager
I wanted to learn the standard observability stack, and to understand why
it's split into three pieces rather than one tool. Prometheus scrapes and
stores metrics (with correct types: counters for cumulative totals, gauges
for current state, histograms for latency distributions, since an average
hides timeout spikes behind a majority of fast successful checks) and
decides when an alert condition is firing. Grafana turns those metrics into
dashboards a human can actually read at a glance during an incident, rather
than reading raw PromQL output. Alertmanager is deliberately a separate
concern from Prometheus: Prometheus decides *if* something is firing,
Alertmanager owns *what happens next* (deduplication, grouping, silencing,
routing to a receiver). Keeping delivery policy out of metric collection is
the point of splitting them into two tools rather than one.

### Docker + Compose
Containers are isolated processes sharing the host kernel, not lightweight
VMs, and Compose orchestrates multiple of them declaratively on one host.
I wanted the whole stack (app, Postgres, Redis, and the observability
tools) to come up with one command and behave identically regardless of
where it runs. As a toy test of that portability, I ran and verified the
full stack on both my personal machine and a second environment
(y540-server, a repurposed laptop running headless Ubuntu Server), not just
locally.


## Data Flow

**1. A target is created.**
`POST /targets` creates an `EndpointTarget` row in Postgres. `enabled`
defaults to `true`, so the target is immediately eligible to be checked,
no separate "activate" step.

**2. The scanner picks it up.**
`target_scanner` runs on a fixed 20s interval, independent of any specific
target. Each run it re-queries Postgres for all `enabled=true` targets and
diffs that against the jobs currently registered in APScheduler. A newly
created target won't have a job yet, so it gets added:
`scheduler.add_job(perform_check, ...)`, on an interval matching that
target's own `interval_seconds`. This means a new target starts being
checked within at most ~20 seconds of creation, not instantly and not on
a restart.

**3. The check itself fires.**
When the per-target job's interval elapses, `perform_check(target_id)`
runs. It re-queries the target's row from Postgres (rather than trusting
whatever was true when the job was scheduled, in case the target was
edited since), then calls `complete_check()`, which makes the actual HTTP
request via `httpx` and returns status code, latency, and (if the request
itself failed, e.g. timeout or DNS failure) an error class.

**4. The result is persisted.**
`record_check_result` writes a new `CheckResult` row to Postgres and
updates `current_failed_checks` on the target (incremented on any error or
failure, reset to 0 on success). If caching is enabled, it also writes a
last-known-status entry to Redis with a TTL. This step is identical
regardless of whether the check succeeded or failed, both outcomes get a
`CheckResult` row and a Prometheus metric update.

**5. Metrics are updated in-process.**
Still inside `perform_check`, `checks_total` (counter) and
`check_latency_seconds` (histogram) are incremented/observed, labeled
`status="success"` or `status="error"`. This is a local, in-memory update.
Nothing is sent anywhere yet, the app has just made its current metric
values available to be read.

**6. Prometheus pulls those values.**
On its own schedule (every 15s, per `prometheus.yml`), Prometheus scrapes
`GET /metrics` on the app container and reads whatever the current
counter/histogram values are at that moment. This is a pull, not a push:
the app never initiates contact with Prometheus, and a check's result
isn't "sent" anywhere the instant it happens, it just sits exposed until
the next scrape picks it up.

**7a. Success path: the metric feeds Grafana.**
Grafana queries Prometheus (via PromQL, e.g. `rate(checks_total[5m])`) to
render dashboard panels. Nothing alert-related happens on this path.

**7b. Failure path: a rule may enter PENDING.**
Separately from scraping, Prometheus continuously evaluates the alert
rules in `alerts.yml` against the metrics it now has. The `TargetDown`
rule (`increase(checks_total{status="error"}[5m]) > 2`) only triggers on
`status="error"`, request-level errors like timeouts, not on a target
that's reachable but returning the wrong status code. If the condition
becomes true, the rule enters `PENDING`, not `FIRING`, yet.

**8. PENDING becomes FIRING.**
`for: 1m` in the rule means the condition has to hold continuously for a
full minute before Prometheus promotes it from `PENDING` to `FIRING`.
This exists specifically to avoid alerting on a single noisy blip.

**9. Alertmanager takes over.**
Only once a rule is `FIRING` does Prometheus hand it to Alertmanager.
Alertmanager owns everything from here: deduplication, grouping, and
routing to a receiver, in this project's case a webhook
(`ALERT_WEBHOOK_URL`). Prometheus's job ends at deciding *if* something is
wrong; Alertmanager's job is deciding *what to do about it*.

## Observability

### Metrics
`/metrics` exposes Prometheus-format metrics: `checks_total` (counter, 
labeled by status/error_class), `check_latency_seconds` (histogram, labeled by status), 
`targets_enabled` (gauge).

### Grafana Dashboard
![Grafana dashboard](docs/screenshots/grafana_dashboard.png)

Four panels: Check Rate by Outcome, Error Check Rate, p95 Latency 
(Success Only), Targets Enabled. Dashboard JSON exported to 
`monitoring/grafana-dashboard.json`.

## AI Usage Disclosure

AI tools were used as learning and documentation aids during this project, not as a code generator.

My primary use of AI was to:
- clarify concepts after reading official documentation
- check whether my understanding of the system architecture was accurate
- reorganize and rewrite notes I had already written
- improve the clarity and structure of README sections, comments, and other documentation
- review explanations of technologies such as SQLAlchemy, Redis, APScheduler, Docker, and FastAPI
- Writing out commit messages

The technical source material came primarily from official documentation and other referenced learning resources. I worked through each concept myself first, then used tools such as ChatGPT or Claude to help turn my own notes into clearer explanations.

**What AI did not do:** I wrote the application logic. I did not use autonomous coding agents or AI-powered CLI tools to generate or modify the project. AI was not used to implement FastAPI route logic, SQLAlchemy models, scheduler and checker behavior, Redis integration, or the health and readiness endpoints, nor was it used to make design decisions (schema design, concurrency settings, error-handling boundaries).

Where AI helped with writing, I reviewed and edited the output myself to make sure I understood it and that it accurately reflected the project's actual implementation.

## Docker Run Instructions

> Ensure that Docker Desktop is running first
1. Copy `.env.example` to `.env` and fill in your credentials:
```
   DATABASE_URL=postgresql://user:password@db:5432/dbname
```


To run the project using docker execute the following commands

2. Build images and run containers:
```bash
docker compose up --build
```
- Note this will fill the terminal with the compose output, include the flag -d to run in detached mode

Once all containers are operational and can communicate with each other:

3. Complete migrations by using the following command
```
docker compose run app alembic upgrade head
```
   - This creates a temporary container that connects to the database and applies our migrations.
   - You could instead use `docker compose exec app alembic upgrade head` if the app container is already running, but using `run` works regardless of whether the stack is up.


4. You can access the application docs here: http://localhost:8000/docs


## Useful Commands For Viewing Logs in Docker Compose

View the logs for all our services:
``` bash
docker compose logs
```

View logs for a specific service:

``` bash
docker compose logs <<service-name>>
```
- Note the service name is outlined in the `docker-compose.yml` file


View logs in real time:
```bash
docker compose logs -f <<service-name>>
```

View only the last `10` lines:

```bash
docker compose logs --tail=10
```

Most useful, Show the last `10` lines in real time for a given service:

```bash
docker compose logs -f --tail=10 <<service-name>> 
```

### Viewing Logs as JSON

To see all jobs that are expected and current:
``` bash
docker compose logs --no-log-prefix app | grep '"level": "info"' | grep '"event": "jobs"' | jq
```

To see check results for expected jobs:
```bash
docker compose logs --no-log-prefix app | grep '"level": "info"' | grep '"event": "check"' | jq
```


To see requests to our process:
```bash

docker compose logs --no-log-prefix app | grep '"event": "request"' | jq
```


To see all errors:
```bash
docker compose logs --no-log-prefix app | grep '"level": "error"' | jq
```


## Running Tests Locally

Tests run on the host machine against the running Docker Compose stack. The stack must be up before running tests.

1. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy `.env.local.example` to `.env.local` and fill in your credentials. Hostnames must use `localhost` instead of the Docker service name `db`:
```
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```
All other variables stay the same as `.env`.

4. Run the test suite:
```bash
pytest
```

`conftest.py` automatically loads both `.env` and `.env.local` before tests run. `.env.local` overrides the Docker hostnames with `localhost` so the local pytest process can reach the database through the exposed port.

> The Docker Compose stack must be running before executing tests. The tests connect to the database through `localhost:5432`, which maps to the `db` container via the port binding in `docker-compose.yml`.
