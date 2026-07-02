import os

from dotenv import load_dotenv
from sqlalchemy.exc import OperationalError

load_dotenv(override=True, interpolate=True)
load_dotenv(".env.test")
from fastapi.testclient import TestClient
from app.main import app
from app.main import get_db


client = TestClient(app)

class MockSession():
    def execute(self, query_text):
        raise OperationalError("Test Connection Lost", params=None, orig=None)



def database_down_override():
    session = MockSession()
    yield session

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready():
    response = client.get("/ready")
    print(response)
    assert response.status_code == 200
    assert response.json() =={"status": "ok", "dependencies": {"db": "ready", "redis": "pending"}}


def test_ready_db_down():
    app.dependency_overrides[get_db] = database_down_override
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "ok", "dependencies": {"db": "down", "redis": "pending"}}
    app.dependency_overrides.clear()
