import redis
import os
from dotenv import load_dotenv

load_dotenv()

# redis.Redis.from_url creates a connection pool, not a single live
# connection. It's built once here at module import time and shared
# across the whole app, same pattern as the SQLAlchemy engine in db.py.
# from_url() doesn't connect eagerly, so a bad/missing REDIS_URL won't
# fail here; it'll fail on the first actual command against Redis.
#
# decode_responses=True makes Redis replies come back as Python str
# instead of bytes, so callers don't need to .decode() every value.
r = redis.Redis.from_url(os.environ['REDIS_URL'], decode_responses=True)


def get_rd():
    # Exists so Redis can be injected via FastAPI's Depends(), the same
    # pattern as get_db(). Returns the shared client above rather than
    # creating a new connection per request.
    return r
