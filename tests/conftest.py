import os
from dotenv import load_dotenv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# .env holds the full set of variables the app needs, loaded first so
# every key exists even if .env.local doesn't override it.
# .env.local (gitignored, documented via .env.local.example in the README)
# then overrides specific values for the local/debugger test run. This
# exists because the local debugger process doesn't automatically inherit
# shell-exported environment variables the way `docker compose` does, so
# credentials can't just be exported into the machine's environment directly
# without leaking them outside of .env-based config.
load_dotenv(ROOT / '.env')
load_dotenv(ROOT / '.env.local', override=True)


import pytest
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db
from sqlalchemy import create_engine


Session = sessionmaker()
engine = create_engine(os.environ['TEST_DATABASE_URL'])
client = TestClient(app)


# pytest fixtures allow us to not have to repeat repetitive code
@pytest.fixture
# we give it a descriptive name, since this fixtures purpose is to create our session
def db_session():
    # Savepoint-based test isolation: each test runs inside an outer
    # transaction that is ALWAYS rolled back in teardown, regardless of
    # whether the test itself calls session.commit(). This means test code
    # can call db.commit() exactly like production code does (no special
    # test-only behavior to remember), while nothing a test does ever
    # actually lands in the test database permanently. Tests stay isolated
    # from each other without needing to truncate/reset tables between runs.
    connection = engine.connect()
    trans = (
        connection.begin()
    )  # outer transaction -- never commits to the database, rolled back in teardown
    session = Session(
        bind=connection, join_transaction_mode='create_savepoint'
    )   # changes sessions so they aren't commited to the database and are instead savepoints

    # inner function that will override the get_db dependency
    # we define it here so that session is known in variable scope and that FastAPI can see it
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    # everything before the yield is setup
    yield session
    # everything after the yield is teardown
    session.close()
    trans.rollback()
    connection.close()
    app.dependency_overrides.clear()   # removes the override so it doesn't impact other tests
