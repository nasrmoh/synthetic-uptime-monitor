# Jun 8 — Prometheus Metric Types

## Why metric types exist at all

A number on its own is ambiguous. Knowing a value is `100` tells us nothing about how it behaves over time, whether it only grows, whether it can drop, or whether it represents a distribution of many individual observations. Prometheus's three metric types exist to remove that ambiguity, and PromQL functions like `rate()` and `histogram_quantile()` depend on knowing which type they're operating on.

## Counter

Monotonically increasing. Only goes up, or resets to zero (process restart).

We used this for `checks_total`, labeled by `status` (`success`/`failure`) and `error_class` (the exception class name from `checker.py`'s except block, or `"none"` on success). Every completed check increments it exactly once, in `perform_check`, right after `record_check_result` runs.

We read counters with `rate()`, which converts a monotonic total into a per-second growth rate. `rate()` assumes monotonicity to survive process restarts cleanly. Say a counter goes 200 → 300 → (crash, resets to 0) → 50. A naive `(end - start) / time` would compute `(50 - 200) / time`, a negative rate, meaningless. `rate()` recognizes the drop as a reset and instead treats it as the counter continuing from where it left off, effectively computing `(300 - 200) + 50` worth of increase over the window. This only works because counters are defined to never decrease except via a full reset to zero. Feeding non-monotonic data into `rate()` breaks this assumption. Ordinary fluctuation looks like repeated resets, and `rate()` overcompensates, inflating the rate every time the value happens to dip.

This is exactly why `enabled_targets` had to be a Gauge and not a Counter, the count of enabled targets can legitimately go down (someone disables a target), and that's a normal state change, not a crash to recover from.

We confirmed the auto-suffix behavior empirically: `Counter("checks", ...)` renders as `checks_total` in `/metrics`, and `prometheus_client` also auto-generates a companion `checks_created` gauge (creation timestamp) we didn't ask for but don't need to worry about.

## Gauge

A snapshot value that can move in either direction.

We used this for `targets_enabled`. It's set inside `target_scanner`, which already queries the current set of enabled targets (`expected_ids`) as part of its normal job of reconciling scheduled jobs against the DB. Setting `targets_enabled.set(len(expected_ids))` there is free, no extra query needed, since the scanner already has to fetch that set.

The tradeoff is staleness. The gauge only updates once per scan cycle (currently ~20-30s), not the instant a target is enabled or disabled via the API. We considered updating it directly in the CRUD routes instead, which would be immediately accurate, but that means either an extra `COUNT(*)` query on every mutation, or maintaining a separate in-memory counter that can silently drift from the DB if any code path bypasses it. We decided the scanner-based approach is fine for now: it mirrors a staleness tradeoff we'd already accepted for job scheduling itself, and the scan interval is a knob we can tighten later if freshness actually becomes a problem.

## Histogram

Buckets observations so we can estimate percentiles cheaply, instead of relying on a mean that hides the tail.

Example: if 9,999 requests load in 10ms and one request times out at 30s, the average is dragged down to a deceptively fine-looking ~13ms. A histogram lets us ask "what's the 95th or 99th percentile," which actually surfaces that slow outlier instead of burying it.

We used this for `check_latency_seconds`. Bucket boundaries went through a few iterations. We started with generic-looking boundaries stretching to 60s, then to 40s, but neither was based on real data. Once we checked actual observed latency (0.2-0.45s for our current targets), we rebucketed to `[0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]`, dense resolution where real traffic actually lands, coarser at the tail to still catch timeouts. Generic default buckets would have crowded all our real observations into one or two buckets and made percentile estimates nearly meaningless.

We verified this with `histogram_quantile(0.95, rate(check_latency_seconds_bucket[5m]))`, which returned a sane p95 (~0.48s cooling to ~0.29s as more fast checks accumulated in the rolling window), consistent with our known latency range. This is the actual query we'd put on a dashboard or alert rule, not the raw `_bucket` series, which is cumulative per threshold (`le="0.5"` includes everything `le="0.3"` counted) and isn't meant to be read directly as a distribution shape. A proper bucket-count or heatmap visualization is Grafana's job, next keystone, not something Prometheus's own graph view is built to render well.

## `perform_check` placement

Both `checks_total` and `check_latency_seconds` are recorded inside `perform_check`, right after `record_check_result`, using the dict already returned by `complete_check`. `complete_check` itself stays pure and side-effect-free, no metric calls inside it, matching the same reasoning that already kept it separate from persistence: it needs to remain testable with a mocked `httpx` call and no other side effects. `perform_check` is the right place because it's already the caller that knows the full outcome and already does the equivalent bookkeeping for persistence and logging.

## Scrape config

`prometheus.yml` scrapes `app:8000`, the Compose service name for the FastAPI app, not `localhost`. `localhost` inside the `prometheus` container resolves to the `prometheus` container itself, not any other container. This is the same internal-DNS mechanism already used for `/ready` checking `db` and `redis` by service name back on May 26. Scrape interval is set to 15s globally.

## Evidence

- `curl /metrics` output showing `checks_total`, `check_latency_seconds`, `targets_enabled` all present with correct `# TYPE` lines and real, non-zero data
- Prometheus Targets page showing `synthetic-uptime-monitor` job as UP
- `checks_total` graph in the Prometheus expression browser showing the expected counter staircase shape





