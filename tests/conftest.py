import os
from contextlib import contextmanager

from dotenv import load_dotenv
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.local", override=True)
print("DATABASE_URL:", os.environ["DATABASE_URL"])
print("TEST_DATABASE_URL:", os.environ["TEST_DATABASE_URL"])


import pytest
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db
from sqlalchemy import create_engine


Session = sessionmaker()
engine = create_engine(os.environ["TEST_DATABASE_URL"])
client = TestClient(app)


# pytest fixtures allow us to not have to repeat repetitive code
@pytest.fixture
# we give it a descriptive name, since this fixtures purpose is to create our session
def db_session():
    connection = engine.connect()
    trans = connection.begin()  # outer transaction -- never commits to the database, rolled back in teardown
    session = Session(bind=connection, join_transaction_mode="create_savepoint") #changes sessions so they aren't commited to the database and are instead savepoints
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
    app.dependency_overrides.clear() # removes the override so it doesn't impact other tests