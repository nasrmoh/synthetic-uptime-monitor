`8.145 sum / 40 count ≈ 200ms` average latency, consistent with all 40
checks landing in the 0.2–0.3s bucket.

## Grafana

Grafana is the visualization layer for the monitoring stack. It reads
metrics from a datasource, in our case Prometheus, and presents them as
dashboards and panels, making system health, failures, and performance
trends legible at a glance. Grafana does not create or collect metrics
itself, it only queries and renders what Prometheus already has.

## Adding Grafana to Docker Compose

```yml
grafana:
  image: grafana/grafana
  environment:
    - GF_SECURITY_ADMIN_USER=${GF_SECURITY_ADMIN_USER}
    - GF_SECURITY_ADMIN_PASSWORD=${GF_SECURITY_ADMIN_PASSWORD}
  ports:
    - "3000:3000"
```

## Provisioning the Prometheus Datasource

Grafana's web UI can add a datasource interactively, it just asks for a
URL (`http://prometheus:9090` in our case, resolved via Compose's internal
DNS). We chose not to do it that way, since a UI-only setup isn't tracked
anywhere in version control, and Grafana ships a provisioning system built
for exactly this: config files it reads on startup.

We created `/monitoring/grafana/provisioning/datasources/prometheus-datasources.yml`:

```yml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    url: ${PROMETHEUS_URL}
```

Then mounted it into the path Grafana expects
(`/etc/grafana/provisioning/datasources/`):

```yml
grafana:
  volumes:
    - ./monitoring/grafana/provisioning/datasources/prometheus-datasources.yml:/etc/grafana/provisioning/datasources/prometheus-datasources.yml
```

## Our First Panel Using `rate`

To exercise the error path, one of our three targets is deliberately set
to `https://this-domain-should-not-exist-used-for-testing-errors.invalid`,
which makes `httpx.get()` raise `httpx.ConnectError`. So we have two real,
working targets and one intentionally broken one.

We built four panels:

- **Check Rate by Outcome (5m)** — success vs. error throughput
- **Error Check Rate (5m)** — isolated failure rate
- **p95 Latency (Success Only)** — tail latency, successful checks only
- **Enabled Targets** — current enabled-target count

Units were converted from req/s to req/min (`rate(...) * 60`) since our
check interval is slow enough that req/s values were all small decimals,
hard to read at a glance. `req/min` is more legible at our volume.

### Bug: latency histogram was missing its `status` label

While building the p95 panel, we discovered `check_latency_seconds`
carried no `status` label at all, even though we intended to filter it the
same way we filter `checks_total`. The instrumentation code was:

```python
check_latency_seconds.observe(check_data["latency_ms"] / 1000, status="success")
```

This is wrong. `Histogram.observe()` does not accept label kwargs, labels
must be bound first via `.labels(...)`, which returns a child metric, and
only then do you call `.observe()` on that child. `total_checks` already
followed this pattern correctly:

```python
total_checks.labels(status="success", error_class="none").inc(1)
```

Fix: declare `labelnames=["status"]` on the `Histogram` at creation time
(it wasn't there originally either), then call it the same way as the
counter:

```python
check_latency_seconds.labels(status="success").observe(check_data["latency_ms"] / 1000)
```

Verified via `/metrics` output — `check_latency_seconds_bucket{status="success", le="..."}`
lines now show up with the label attached, where before the label was
silently absent and no `status`-filtered query could ever return data.

### Why the histogram needed filtering at all

Errors (`ConnectError` against the `.invalid` domain) fail almost
instantly, well under 100ms, since a DNS resolution failure never gets to
attempt a TCP handshake. Successful checks take longer, doing a real HTTP
round trip. Mixing both into one latency distribution skews percentiles
downward, making real endpoint performance look faster than it is. This
was confirmed directly against scrape data: with 64 errors and 128
successes, the `le="0.1"` bucket held exactly 64, meaning every single
error fell under 100ms, and successes were the ones spread across
0.1–0.3s. Filtering the p95 query to `status="success"` moved the value
from 0.270s to 0.290s, in the direction predicted (removing a cluster of
near-zero-latency values pushes the percentile up).

### Standardizing `error` vs `failure`

Both `total_checks` and `check_latency_seconds` originally used
inconsistent status label values (`failure` on one, in-progress rename on
the other). Standardized both to `error`, since the label refers
specifically to `httpx` exception classes (`ConnectError`,
`ConnectTimeout`, etc.), not general failure/mismatch cases. This matches
the error-vs-failure distinction already documented in the README for
`CheckResult.error_class`.

## Provisioning the Dashboard

Once the four panels were built and polished (custom legend names,
explicit color mapping, panel descriptions, axis units), we exported the
dashboard JSON and provisioned it the same way as the datasource, so it
loads automatically rather than requiring a manual import on every fresh
environment.

Provisioning config, `/monitoring/grafana/provisioning/dashboards/dashboard.yml`:

```yml
apiVersion: 1

providers:
  - name: Synthetic Uptime Monitor Dashboard
    orgId: 1
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: false
    options:
      path: /etc/grafana/dashboards
```

`allowUiUpdates: false` was a deliberate choice: the committed JSON file
is meant to be the single source of truth for the dashboard's real state.
This is one-directional, `allowUiUpdates` only controls whether Grafana
*keeps or reverts* changes made through its own UI, it does not write UI
edits back out to the file on disk. With it set to `false`, any change
made in the browser gets silently reverted on the next
`updateIntervalSeconds` sync, forcing changes to go through the JSON file
(or a re-export) instead. This keeps the repo from silently drifting out
of sync with what's actually running, at the cost of losing the
convenience of quick UI tweaks.

Exported dashboard JSON goes to `/monitoring/grafana/dashboards/grafana-dashboard.json`.
Final directory layout:
```
monitoring/  
grafana/  
dashboards/  
grafana-dashboard.json  
provisioning/  
dashboards/  
dashboard.yml  
datasources/  
prometheus-datasources.yml
```


Both provisioning file and dashboard JSON get mounted into the container:

```yml
volumes:
  - ./monitoring/grafana/provisioning/datasources/prometheus-datasources.yml:/etc/grafana/provisioning/datasources/prometheus-datasources.yml
  - ./monitoring/grafana/provisioning/dashboards/dashboard.yml:/etc/grafana/provisioning/dashboards/dashboard.yml
  - ./monitoring/grafana/dashboards/grafana-dashboard.json:/etc/grafana/dashboards/grafana-dashboard.json
```
