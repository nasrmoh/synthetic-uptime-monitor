
# Logging Implementation Notes — Jun 4

## Processor chain configuration

Set up once in `main.py`, at startup, before any request comes in:

```python
# Configure structlog's processor chain once at startup.
# Processors run in order, each transforming the event dict and passing it to the next:
#   1. merge_contextvars    -> pulls in anything bound via bind_contextvars() (correlation_id, execution_id)
#   2. TimeStamper          -> adds an ISO 8601 "timestamp" field
#   3. add_log_level        -> adds a "level" field based on which method was called (.info, .error, etc.)
#   4. JSONRenderer         -> serializes the final dict to a JSON string
# JSONRenderer MUST be last: it's the only processor whose output isn't a dict anymore,
# so anything after it would receive a string instead of an event dict and fail.
structlog.configure(processors=[
    structlog.contextvars.merge_contextvars,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.add_log_level,
    structlog.processors.JSONRenderer(),
])
```

## Correlation ID middleware

Correlation IDs need to exist on every request. A `Depends()`-based approach (same pattern as the DB/Redis session injection) was considered, but that only runs for routes that declare it — a route added later without remembering to add the dependency would silently have no correlation id, and a request to a route that doesn't exist at all (404) never resolves to any route function, so it would never reach a dependency in the first place. Middleware sits one layer below routing itself — it wraps every request before FastAPI decides which function to call — so it's the right tool for something that must apply unconditionally, including to unmatched routes.

```python
@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    logger = structlog.get_logger()
    if request.headers.get("X-Correlation-ID"):
        correlation_id = request.headers.get("X-Correlation-ID")
    else:
        correlation_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        duration = time.perf_counter() - start_time
        response.headers["X-Correlation-ID"] = correlation_id
        logger.info("request", method=request.method, path=request.url.path, status_code=response.status_code, duration_ms=duration)
        return response
    except Exception as e:
        logger.error("request", method=request.method, path=request.url.path, exception=type(e).__name__)
        raise e
    finally:
        structlog.contextvars.clear_contextvars()
```

- Reads an incoming `X-Correlation-ID` header if the client (or an upstream gateway) already provided one; otherwise generates a fresh UUID. Honoring an existing header matters if something ever sits in front of this app and forwards its own request id — without it, that id's logs and this app's logs couldn't be joined.
- `try`/`except`/`finally` is the core structure. On success: log at `info`, with the real response status and timing. On an unhandled exception: log at `error` with the exception's class name, then `raise e`. Re-raising the original exception (not a new reference to it) preserves the original traceback and lets it keep propagating past this middleware to Starlette's own error handling, which is what actually builds the client's 500 response. If this exception were swallowed here instead of re-raised, the client would get no response at all, and FastAPI's own error handling would never run.
- `finally: clear_contextvars()` guarantees the bound correlation id is cleared whether the request succeeded or crashed, so it never leaks into whatever request or job reuses this execution context next. Verified empirically: hit a route that deliberately raises, confirmed a `level: error` log line with the exception name and a proper 500 to the client, then hit a separate working route immediately after and confirmed it got its own fresh correlation id with no trace of the crashed request's id.

## Checker logs

```python
def perform_check(target_id):
    execution_id = str(uuid.uuid4())
    logger = structlog.get_logger()
    structlog.contextvars.bind_contextvars(execution_id=execution_id)

    db: Session
    with get_db_with_context() as db:
        # Query the database for the endpoint target
        statement = select(EndpointTarget).where(EndpointTarget.id == target_id)
        res: EndpointTarget | None = db.execute(statement).scalars().first()
        try:
            if res is None:
                logger.error("check", error=TargetNotFoundError.__name__)
                raise TargetNotFoundError("Target ID not found")

            if res.enabled:
                check_data = complete_check(res.url, res.id, res.timeout_seconds)
                record_check_result(
                    db=db, status_code=check_data["status_code"], error_class=check_data["error_class"],
                    target_id=check_data["target_id"], latency_ms=check_data["latency_ms"],
                    endpoint=res, cache=True,
                )
                logger.info("check", target_id=target_id, status_code=check_data["status_code"],
                            latency_ms=check_data["latency_ms"], error_class=check_data["error_class"])
            else:
                logger.info("check", enabled=False)
            # A disabled target reaching this point means the scanner hasn't caught the
            # disable yet (patched to enabled=False, but its check job hasn't been
            # removed from the scheduler). We don't perform the http check or record
            # anything in this case, we just query and stop here.
            # Once the scanner's next pass runs, it will remove this job and no more
            # firings will happen for this target until it's re-enabled.
        finally:
            structlog.contextvars.clear_contextvars()
```

- No `correlation_id` here — a scheduler run isn't triggered by a request, so it gets its own concept, `execution_id`, generated fresh per run and bound the same way. This keeps the two id types honest: `correlation_id` only ever means "this was triggered by an inbound request," `execution_id` only ever means "this was self-triggered work."
- Logging `check_data["status_code"]` rather than `res.expected_status` matters — the former is the actual observed outcome of this specific check, the latter is just the target's static configured expectation. Logging the wrong one would make every log line report the same number regardless of what actually happened.
- Same `try`/`finally` shape as the middleware, for the same reason: guarantee `clear_contextvars()` runs whether the function returns normally or an exception (like `TargetNotFoundError`) propagates out of it.

## Verification performed

- Successful request → `level: info`, correct method/path/status_code/duration, `correlation_id` present and unique per request.
- Deliberately broken route (`raise ValueError`) → `level: error`, exception name captured, client still received a proper `500`, and a subsequent unrelated request got a fresh `correlation_id` with no leakage from the crashed one.
- Checker run → `level: info`, `execution_id` present, `target_id`/`status_code`/`latency_ms`/`error_class` all reflecting the actual check outcome. Two concurrent target checks confirmed to produce two distinct `execution_id`s.
- No `correlation_id` and `execution_id` ever appear on the same log line — confirming the two id types stay correctly scoped to their respective triggers (inbound request vs. self-triggered scheduler run).

















