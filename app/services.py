import json
from datetime import datetime, timezone

import redis.exceptions
from app.models import CheckResult, EndpointTarget
from redis import Redis
from sqlalchemy.orm import Session

FIXED_TTL = 120


def record_check_result(
    db: Session,
    rd: Redis | None,
    status_code,
    error_class,
    target_id,
    latency_ms,
    endpoint: EndpointTarget,
    cache=True,
):
    # Redis is optional (rd can be None) for callers that don't want caching,
    # but if cache=True is requested, a client must actually be provided.
    # Fail loudly here rather than silently skipping the cache write.
    if rd is None and cache:
        raise ValueError('Redis client is required when caching is enabled')

    check_result = CheckResult(
        status_code=status_code,
        error_class=error_class,
        target_id=target_id,
        latency_ms=latency_ms,
    )
    # register object with SQLAlchemy; nothing hits the DB until commit()
    db.add(check_result)

    # status_code is None is technically redundant here (None never equals expected_status),
    # kept explicit for readability: distinguishes "wrong status" from "unreachable" at a glance
    if (status_code != endpoint.expected_status) or (status_code is None):
        endpoint.current_failed_checks += 1
    else:
        endpoint.current_failed_checks = 0

    # Single commit for both the new CheckResult row and the updated
    # current_failed_checks counter, so they land in the DB atomically
    # together rather than as two separate transactions.
    #
    # checks_total / check_latency_seconds metrics are NOT incremented
    # here, the caller has more context (e.g. which stage failed) and is
    # responsible for recording them.
    db.commit()

    if cache:
        try:
            # Timezone-aware, to match Postgres's TIMESTAMPTZ columns
            # (see SQL notes on why TIMESTAMPTZ over TIMESTAMP). This is
            # an approximate timestamp (when this function ran), not the
            # DB-assigned checked_at (server_default=func.now(), set by
            # Postgres at insert time). Close enough for cache/display
            # purposes; the two are not guaranteed to match exactly.
            cache_approx_time = datetime.now(timezone.utc).isoformat()
            json_string = json.dumps(
                {
                    'status_code': status_code,
                    'error_class': error_class,
                    'latency_ms': latency_ms,
                    'checked_at': cache_approx_time,
                }
            )

            # TTL, not permanent: if Redis loses this key, it's treated as
            # "no recent status," not data loss, since Postgres above is
            # the actual source of truth. Key format target:{id}:last_status
            # matches the pattern used elsewhere for per-target Redis state.
            rd.set(
                f'target:{target_id}:last_status', json_string, ex=FIXED_TTL
            )
        except (
            redis.exceptions.TimeoutError,
            redis.exceptions.ConnectionError,
        ) as e:
            # Redis being down must not fail the check result itself, the
            # DB write above has already committed by this point. This is
            # the graceful degradation behavior verified in the May 30 and
            # Jun 7 Redis-down drills.
            print(
                f'Cache failed for {target_id} with the following error: {type(e).__name__}'
            )

    return check_result
