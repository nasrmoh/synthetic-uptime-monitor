"""
FastAPI app entry point and router registration
"""
import redis.exceptions
from app.routers import targets
from fastapi import FastAPI, Depends, status, Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from redis import Redis
from app.db import get_db
from app.cache import get_rd

app = FastAPI()





@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready(response: Response,db : Session = Depends(get_db), rd : Redis = Depends(get_rd)):
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