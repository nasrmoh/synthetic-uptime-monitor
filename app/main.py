"""
FastAPI app entry point and router registration
"""
import time
import uuid
import os
import redis.exceptions
import structlog
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status, Request
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from redis import Redis
from app.db import get_db
from app.cache import get_rd
from app.routers import targets
from app.scanner import target_scanner
from starlette.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

# Configure structlog's processor chain once at startup.
# Processors run in order, each transforming the event dict and passing it to the next:
#   1. merge_contextvars    -> pulls in anything bound via bind_contextvars() (correlation_id, execution_id)
#   2. TimeStamper          -> adds an ISO 8601 "timestamp" field
#   3. add_log_level        -> adds a "level" field based on which method was called (.info, .error, etc.)
#   4. JSONRenderer         -> serializes the final dict to a JSON string
# JSONRenderer MUST be last: it's the only processor whose output isn't a dict anymore,
# so anything after it would receive a string instead of an event dict and fail.
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt='iso'),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

scheduler = AsyncIOScheduler()


# FastAPI's lifespan context manager: code before `yield` runs on startup,
# code after `yield` runs on shutdown. This is where APScheduler gets wired
# in, rather than using the deprecated @app.on_event("startup") pattern.


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Parse SCHEDULER_ENABLED strictly rather than using a truthy check like
    # bool(os.environ["SCHEDULER_ENABLED"]), since any non-empty string
    # (including "False") would evaluate to True. Fail loudly on anything
    # other than the two expected values instead of silently defaulting.
    if os.environ['SCHEDULER_ENABLED'] == 'True':
        res = True
    elif os.environ['SCHEDULER_ENABLED'] == 'False':
        res = False
    else:
        raise ValueError(
            'Invalid Configuration for SCHEDULER_ENABLED Environment Variable'
        )

    if res:
        # max_instances=1 prevents overlapping runs of target_scanner if one
        # scan takes longer than the 20s interval, which would otherwise let
        # concurrent scans race on the same targets (see notes on
        # current_failed_checks lost-update risk).
        # misfire_grace_time=2 allows a run to still fire if it's up to 2s
        # late (e.g. due to load), rather than being skipped entirely.
        scheduler.add_job(
            target_scanner,
            trigger='interval',
            seconds=20,
            id='target_scanner',
            args=[scheduler],
            max_instances=1,
            misfire_grace_time=2,
        )
        scheduler.start()
        yield
        scheduler.shutdown()
    else:
        # Scheduler disabled: app still starts and serves requests
        # (e.g. /health, /ready, manual endpoints), it just never
        # schedules background checks. Used for the SCHEDULER_ENABLED
        # drill to observe stale results without a working scheduler.
        yield


app = FastAPI(lifespan=lifespan)

# Middleware runs on every incoming request, before routing decides which
# endpoint (if any) handles it. That's why this lives here instead of inside
# individual routes: it guarantees every request gets a correlation ID and a
# logged entry, including 404s and requests to endpoints that don't exist.
# It also gives us per-request timing without adding timing code to every
# route by hand.
@app.middleware('http')
async def add_correlation_id(request: Request, call_next):
    logger = structlog.get_logger()

    # Reuse an incoming correlation ID if one was passed (e.g. from an
    # upstream caller tracing the request across services). Otherwise
    # mint a new one so this request still gets one consistent ID.
    if request.headers.get('X-Correlation-ID'):
        correlation_id = request.headers.get('X-Correlation-ID')
    else:
        correlation_id = str(uuid.uuid4())

    # Bind the correlation ID into structlog's context so it's automatically
    # attached to every log line emitted during this request, without having
    # to pass correlation_id= manually into each log call downstream.
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        duration = time.perf_counter() - start_time

        # Echo the correlation ID back so the caller can match their own
        # logs against ours.
        response.headers['X-Correlation-ID'] = correlation_id

        logger.info(
            'request',
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration,
        )
        return response
    except Exception as e:
        # Log before re-raising so the exception still propagates normally
        # (FastAPI's own exception handlers still run after this).
        logger.error(
            'request',
            method=request.method,
            path=request.url.path,
            exception=type(e).__name__,
        )
        raise e
    finally:
        # Without this, bound contextvars can leak into whatever request
        # gets handled next on this worker if the runtime reuses context.
        structlog.contextvars.clear_contextvars()


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/broken')
def broken():
    raise ValueError('this is for testing')


@app.get('/ready')
def ready(
    response: Response,
    db: Session = Depends(get_db),
    rd: Redis = Depends(get_rd),
):
    response.status_code = status.HTTP_200_OK
    app_status = 'ok'
    rd_status = 'ready'
    db_status = 'ready'

    # Try to reach Redis
    try:
        rd.ping()
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
        rd_status = 'down'
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Try to reach Postgres
    db_test_text = text('SELECT 1')
    try:
        db.execute(db_test_text)
    except OperationalError:
        db_status = 'down'
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    if rd_status == 'down' or db_status == 'down':
        app_status = 'unavailable'

    return {
        'status': app_status,
        'dependencies': {'db': db_status, 'redis': rd_status},
    }


app.include_router(targets.router, prefix='/targets')


@app.get('/metrics')
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
