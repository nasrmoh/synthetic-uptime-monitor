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


## How the scheduler works

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

## Architecture Vision
- A synthetic uptime monitor which sends HTTP requests to a list of some target URLs then records the response time and status codes, which will be stored in a PostgreSQL database. Redis is used to hold short lived operational states, for example the last known target status. 
The metrics will be exposed via Prometheus, visualized using Grafana, and finally routed using Alertmanager

## Architcture Diagram 
- To be Added

## Technology Rationale
- FastAPI over Django:
  - I wanted to use a pure JSON API, Django is a "batteries-included" framework, it provides things like HTML templates, admin dashboard, and ORM that I didn't really think were necessary here. Something lighter like FastAPI was more important to me
- PostgreSQL:
  - Persistent storage
- Redis:
  - I wanted a form of fast in-memory caching that's safe to rebuild from if something happens to Postgres   
- Promethues + Grafana + Alertmanager:
  -  I wanted to learn the standard observability stack where metrics were collected, visualized, and alerts were routed as a separate concern
- Docker + Compose:
  - I wanted something that would work in multiple different environments, and a system to easily run everything.


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