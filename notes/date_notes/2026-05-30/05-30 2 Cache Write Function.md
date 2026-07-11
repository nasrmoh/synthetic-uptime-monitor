**Where does this function get called?**

Currently we manually create `CheckResult` in the function `record_check_result`, which takes in a `db` session and the necessary information to build the database row.

We decided it makes the most sense to have `rd` also be passed to the function. That way, since we already have the information needed, we can insert into the database and then automatically also cache the value.

Issue is that this sort of binds the two together. Now every manual insertion is also a cache. We can alter the function signature to require a parameter flag such that if true we cache, and if not true we don't cache. That way the function automatically caches, and we have to specifically tell it not to via the flag.

- Needs an assert in the case that the flag is set to true but no `rd` client is passed.
- That way tests can decide not to cache the value, since we don't really have something right now set up to test our caches.

**Which values should we cache?**

- `target_id` isn't necessary, it's redundant since the key itself is `target:<id>:last_status`, so anyone reading the key already knows the target.
- What we do include: `status_code`, `error_class`, `latency_ms`, `checked_at`.

**How do we serialize the value?**

Redis stores strings, so the dict we build gets passed through `json.dumps` before writing. The one field that needs handling is `checked_at`, since `json.dumps` can't serialize a raw `datetime` on its own. We're converting it to a string with `.isoformat()` before it goes into the dict, rather than giving `json.dumps` a `default=` handler, since that's less code and we don't need it back as a real `datetime` object anywhere today, a plain string is fine to read or log.

This connects to a separate issue we hit: `checked_at` on the model is a `server_default=func.now()`, meaning Postgres generates it at insert time, not Python. That value isn't available to `record_check_result` at the point it receives its parameters. Rather than doing a `db.refresh()` round-trip to pull the real Postgres-generated timestamp back, we're using `datetime.now()` in Python right before caching. This is a deliberate simplification, worth an explicit comment in the code, since this function only exists to manually exercise the cache pattern before a real checker flow exists. The few milliseconds of drift between the Python timestamp and the actual Postgres-stamped value don't matter for a cache that's already disposable and TTL-bounded.

**What TTL do we use?**

A fixed constant for now, somewhere in the 60-120 second range. This isn't derived from a target's `interval_seconds` because there's no scheduler yet to read that value from. Worth revisiting once the real checker flow exists in Week 2.

**What happens if the Redis write fails?**

The try/except lives inside the function itself, not the caller. It catches `redis.exceptions.ConnectionError` and `redis.exceptions.TimeoutError`, the two failure types verified empirically earlier today by stopping the Redis container and reading the raised exception directly. On failure, it logs and returns quietly rather than propagating. This keeps the guarantee we care about intact: a Redis outage can never fail the Postgres write, since the insert has already succeeded by the time the cache step runs.