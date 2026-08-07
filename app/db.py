"""
Database engine, session factory, and get_db dependency
"""
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from contextlib import contextmanager
import os


# Engine is created at import time, so if DATABASE_URL is not configured, the app crashes on startup.
# The engine is our low-level connection to the database.
# It manages the connection pool and handles communication with Postgres.
engine = create_engine(os.environ['DATABASE_URL'])

# SessionLocal is a factory (a function whose job is to make things).
# Specifically, it knows how to make sessions.
# Calling SessionLocal() creates a new session instance.
SessionLocal = sessionmaker(engine)


def get_db():
    # FastAPI dependency. FastAPI knows how to drive a generator dependency:
    # it calls next() to get the yielded session, hands it to the route,
    # then resumes the generator (running the finally block) once the
    # route finishes. This only works inside FastAPI's request lifecycle.
    session = SessionLocal()
    try:
        yield session  # hand over the session to a route
    finally:
        session.close()  # close the session


@contextmanager
def get_db_with_context():
    # scanner.py and checker.py need a database session too, but they run
    # outside FastAPI's request lifecycle, so there's nothing to drive
    # get_db()'s generator the way FastAPI does.
    #
    # get_db_with_context() delegates to get_db() rather than duplicating
    # its body. Calling get_db() doesn't run any of its code yet, since
    # it's a generator function; it just returns a generator object.
    # Returning that object here means @contextmanager ends up wrapping
    # the exact same generator get_db() would have produced, so entering
    # this context manager runs get_db()'s body up to `yield session`,
    # and exiting it resumes into the `finally: session.close()` block.
    #
    # This gives scanner/checker code a `with get_db_with_context() as db:`
    # usage pattern with the identical session lifecycle as the FastAPI
    # dependency, without copy-pasting the session/try/finally logic.
    return get_db()
