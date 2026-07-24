**May 26 — DB Dependency + `/ready` Postgres Check**

**`get_db` — Session Dependency (`app/db.py`)**

Added `SessionLocal` and `get_db` to `app/db.py`. `get_db` is a generator function -- FastAPI calls it before the route runs, injects the session, and guarantees the `finally` block runs after.

python

```python
SessionLocal = sessionmaker(engine)

def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

**`/ready` — Postgres Health Check (`app/main.py`)**

Updated `/ready` to run a `SELECT 1` against Postgres using the injected session. Returns 200 when healthy, 503 on `OperationalError`.

python

```python
@app.get("/ready")
def ready(response: Response, db = Depends(get_db)):
    db_test_text = text("SELECT 1")
    response.status_code = status.HTTP_200_OK
    try:
        db_result = db.execute(db_test_text)
        db_status = "ready"
    except OperationalError:
        db_status = "down"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok", "dependencies": {"db": db_status, "redis": "pending"}}
```

**Testing Setup**

There was an issue with `DATABASE_URL` -- the Compose stack resolves the host as `db` (the Docker service name), but pytest running locally has no idea what `db` refers to. Fixed by adding a `.env.test` file with `DATABASE_URL` pointing to `localhost:5432` instead. `.env` holds the credentials, `.env.test` holds the resolved `DATABASE_URL` for local testing. Tests call `load_dotenv()` twice, loading `.env` first so the credentials are available for interpolation, then `.env.test` to override `DATABASE_URL`.

**Testing `/ready` with a Simulated Database Failure**

`/ready` catches `OperationalError` inside a `try` block -- so to test the failure path, we need that exception to be raised when `db.execute()` is called. Simply raising it in the dependency override doesn't work because the exception fires during dependency resolution, before the route's `try` block ever runs.

The fix is `app.dependency_overrides` -- FastAPI lets you swap out any dependency for a test-specific version without touching route code. The override needs to be a generator like `get_db`, and it needs to yield something that looks like a session. So we created a `MockSession` class whose `execute` method raises `OperationalError`, and yielded that instead of a real session.

python

```python
class MockSession:
    def execute(self, query_text):
        raise OperationalError("Test Connection Lost", params=None, orig=None)

def database_down_override():
    session = MockSession()
    yield session

def test_ready_db_down():
    app.dependency_overrides[get_db] = database_down_override
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "ok", "dependencies": {"db": "down", "redis": "pending"}}
    app.dependency_overrides.clear()
```

`app.dependency_overrides.clear()` is called after the test so the override doesn't bleed into other tests.


**Regular flow:**
```
request → /ready → FastAPI calls get_db() → yields real session → db.execute(SELECT 1) → returns 200
```

**Test flow:**
```
request → /ready → FastAPI calls database_down_override() → yields MockSession → db.execute(SELECT 1) → MockSession.execute() raises OperationalError → except block catches it → returns 503
```

The route code never changes -- it just receives whatever the dependency provides. In production that's a real SQLAlchemy session. In the test it's a `MockSession` that raises on `execute()`. The route has no idea which one it got.