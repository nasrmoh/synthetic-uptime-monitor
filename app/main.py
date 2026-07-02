import sqlalchemy
from fastapi import FastAPI
from app.db import get_db
from fastapi import Depends
from fastapi import Response, status
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

app = FastAPI()






@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready(response: Response,db = Depends(get_db)):
    db_test_text = text("SELECT 1")
    response.status_code = status.HTTP_200_OK
    try:
        db_result = db.execute(db_test_text)
        db_status = "ready"
    except OperationalError:
        db_status = "down"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok", "dependencies": {"db": db_status, "redis": "pending"}}
