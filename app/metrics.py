from prometheus_client import Counter, Histogram, Gauge
total_checks = Counter("checks", "the total number of checks completed", labelnames=["target_id", "status", "error_class"])
hbuckets = [0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
check_latency_seconds = Histogram("check_latency_seconds", "latency histogram for checks", labelnames=["status"], buckets=hbuckets)
targets_enabled = Gauge("targets_enabled", "The number of our targets that are currently enabled")

