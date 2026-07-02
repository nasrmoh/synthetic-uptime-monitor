"""
Database engine, session factory, and get_db dependency
"""
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os

# Engine is created at import time, so if "DATABASE_URL" is not configured, then the App will crash
# The engine is our low-level connection to the database.
# It manages the connection pool and handles communication with Postgres.
engine = create_engine(os.environ["DATABASE_URL"])

# SessionLocal is a factory (a function whose job is to make things).
# Specifically, it knows how to make sessions
# calling SessionLocal() will create a new session instance.
SessionLocal = sessionmaker(engine)


def get_db():
    # Create a new session instance
    session = SessionLocal()
    try:
        yield session # hand over the session to a route
    finally:
        session.close() # close the session




