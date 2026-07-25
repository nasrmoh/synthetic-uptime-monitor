"""
FastAPI app entry point and router registration
"""
import time
import uuid

import redis.exceptions
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status, Response, Request
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

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(target_scanner, trigger="interval", seconds = 20, id="target_scanner", args=[scheduler], max_instances=1)
    scheduler.start()
    yield
    scheduler.shutdown()
app = FastAPI(lifespan=lifespan)


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
        logger.error("request", method=request.method, path=request.url.path, exception = type(e).__name__)
        raise e
    finally:
        structlog.contextvars.clear_contextvars()










@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/broken")
def broken():
    raise ValueError("this is for testing")

@app.get("/log")
def log():
    structlog.get_logger().info("temp_event", target_id=18)
    return {"status" : "ok"}

@app.get("/ready")
def ready(response: Response, db : Session = Depends(get_db), rd : Redis = Depends(get_rd)):
    response.status_code = status.HTTP_200_OK
    app_status = "ok"
    rd_status = "ready"
    db_status = "ready"

    # Try to reach Redis
    try:
        rd.ping()
    except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError):
        rd_status = "down"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    # Try to reach Postgres
    db_test_text = text("SELECT 1")
    try:
        db.execute(db_test_text)
    except OperationalError:
        db_status = "down"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    if rd_status == "down" or db_status == "down":
        app_status = "unavailable"

    return {"status": app_status, "dependencies": {"db": db_status, "redis": rd_status}}

app.include_router(targets.router, prefix="/targets")