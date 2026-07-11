import json
from datetime import datetime

import redis.exceptions
from app.models import CheckResult
from redis import Redis
from sqlalchemy.orm import Session

FIXED_TTL = 80


def record_check_result(db : Session, rd : Redis, status_code, error_class, target_id, latency_ms, cache=True):
    if rd is None and cache:
        raise ValueError("Redis client is required when caching is enabled")

    check_result = CheckResult(status_code=status_code, error_class=error_class, target_id = target_id, latency_ms = latency_ms)
    # register object with SQLAlchemy
    db.add(check_result)
    db.commit()


    if cache:
        try:
            # Note that we use an approximation of the cache time. instead of pulling the value for postgres.
            # We can change this later. if needed.
            cache_approx_time = datetime.now().isoformat()
            json_string = json.dumps({"status_code" : status_code, "error_class" : error_class, "latency_ms" : latency_ms, "checked_at" : cache_approx_time})
            rd.set(f"target:{target_id}:last_status", json_string, ex=FIXED_TTL)
        except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError) as e:
            print(f"Cache failed for {target_id} with the following error: {type(e).__name__}")

    return check_result