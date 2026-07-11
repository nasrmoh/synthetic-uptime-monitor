import redis.exceptions
from sqlalchemy.exc import OperationalError
from app.main import app
from app.db import get_db
from app.cache import get_rd
from tests.conftest import client


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() =={"status": "ok", "dependencies": {"db": "ready", "redis": "ready"}}


def test_ready_db_down():
    # this test tests that the case where the database is down and returns the correct message / status code


    class MockSession:
        # ready() only calls session.execute(), so our mock session only needs
        # to implement execute(). Calling it always raises an OperationalError
        # to simulate the database being unavailable.
        def execute(self, query_text):
            raise OperationalError("Test Connection Lost", params=None, orig=None)

    def database_down_override():
        # get_db() is a generator dependency that yields a database session.
        # We replace it with a generator that yields our mock session instead.
        session = MockSession()
        yield session

    app.dependency_overrides[get_db] = database_down_override # we override to introduce our own dependency
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["db"] ==  "down"
    app.dependency_overrides.pop(get_db, None) # reset so other functions get back the original form of get_db



def test_ready_rd_down():
    class MockRedisClient:
        def ping(self):
            raise redis.exceptions.ConnectionError
    def redis_down_override():
        return MockRedisClient()
    app.dependency_overrides[get_rd] = redis_down_override
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["redis"] == "down"
    app.dependency_overrides.pop(get_rd, None) # reset override
