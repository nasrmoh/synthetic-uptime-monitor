"""
FastAPI app entry point and router registration
"""
from app.routers import targets
from fastapi import FastAPI, Depends, status, Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from app.db import get_db


app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready(response: Response,db = Depends(get_db)):
    db_test_text = text("SELECT 1")
    response.status_code = status.HTTP_200_OK

    try:
        db.execute(db_test_text)
        db_status = "ready"
    except OperationalError:
        db_status = "down"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok", "dependencies": {"db": db_status, "redis": "pending"}}

app.include_router(targets.router, prefix="/targets")
