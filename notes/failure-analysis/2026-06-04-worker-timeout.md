## Drill: worker timeout / thread exhaustion

The prescribed drill (register a target against a slow endpoint with an interval shorter
than the response time, observe thread pool exhaustion, then add an explicit httpx timeout
to fix it) does not apply as written to this system, because the mitigation it's meant to
teach is already a structural constraint here, not something added reactively.

- `EndpointTarget.timeout_seconds` is enforced at [validation point — e.g., Pydantic schema /
  route validation] to be less than `interval_seconds` at creation/update time.
- `complete_check` passes `timeout=res.timeout_seconds` directly into the httpx call — there
  is no separate, unbounded default timeout path a check could fall through to.

