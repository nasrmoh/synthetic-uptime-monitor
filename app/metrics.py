from prometheus_client import Counter, Histogram, Gauge

# Counter: monotonically increasing, only valid to read via rate()/increase().
# labelnames create a separate time series per unique combination of
# (target_id, status, error_class). target_id cardinality is a known
# tradeoff
total_checks = Counter(
    'checks',
    'the total number of checks completed',
    labelnames=['target_id', 'status', 'error_class'],
)

# Bucket boundaries in seconds. Fine-grained under 1s to distinguish fast
# successful checks, coarser above that up to 30s to cover slow requests
# and timeouts.
hbuckets = [0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]

# Histogram: buckets observations so p95/p99 can be computed via
# histogram_quantile() instead of relying on a mean, which hides timeout
# spikes behind a majority of fast successful checks.
# labelnames=["status"] lets latency be queried separately for successes
# vs errors; near-instant failures would otherwise skew the distribution
# if mixed in with successful checks.
check_latency_seconds = Histogram(
    'check_latency_seconds',
    'latency histogram for checks',
    labelnames=['status'],
    buckets=hbuckets,
)

# Gauge: goes up and down, unlike a counter. Reflects current state
# (how many targets are enabled right now), not a cumulative total.
targets_enabled = Gauge(
    'targets_enabled', 'The number of our targets that are currently enabled'
)
