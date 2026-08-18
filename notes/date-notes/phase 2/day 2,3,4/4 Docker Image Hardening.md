# Docker Image Hardening

## Before `.dockerignore` update

```
CONTAINER                                 REPOSITORY                     TAG      SIZE     CREATED
synthetic-uptime-monitor-alertmanager-1   prom/alertmanager              latest   39.8MB   6 weeks ago
synthetic-uptime-monitor-app-1            synthetic-uptime-monitor-app   latest   89.4MB   13 seconds ago
synthetic-uptime-monitor-db-1             postgres                       latest   162MB    3 months ago
synthetic-uptime-monitor-grafana-1        grafana/grafana                latest   378MB    4 weeks ago
synthetic-uptime-monitor-prometheus-1     prom/prometheus                latest   107MB    2 weeks ago
synthetic-uptime-monitor-redis-1          redis                          latest   54.3MB   2 months ago
```

Total stack: ~830MB across all six services (roughly 900MB accounting for shared base layers and overhead).

## `.dockerignore` added

```
.venv
.env.*
.env
__pycache__
.git/
docs
notes
tests
.pytest_cache/
monitoring
*.md
```

## After `.dockerignore` update

```
CONTAINER                                 REPOSITORY                     TAG      SIZE     CREATED
synthetic-uptime-monitor-alertmanager-1   prom/alertmanager              latest   39.8MB   6 weeks ago
synthetic-uptime-monitor-app-1            synthetic-uptime-monitor-app   latest   89.2MB   9 seconds ago
synthetic-uptime-monitor-db-1             postgres                       latest   162MB    3 months ago
synthetic-uptime-monitor-grafana-1        grafana/grafana                latest   378MB    4 weeks ago
synthetic-uptime-monitor-prometheus-1     prom/prometheus                latest   107MB    2 weeks ago
synthetic-uptime-monitor-redis-1          redis                          latest   54.3MB   2 months ago
```

**App image: 89.4MB → 89.2MB (~200KB reduction).**

## Reading the result honestly

The size delta is small, and that's expected rather than a sign the exclusion didn't work. `notes/`, `docs/`, and `tests/` are text files — a few hundred KB at most for a project this size — against an 89MB image dominated by the Python base layer and installed dependencies. A large before/after gap was never realistic here. 

The other five services (Postgres, Redis, Prometheus, Grafana, Alertmanager) are unaffected by this `.dockerignore`, as expected — it only scopes the app's own build context. Their sizes are exactly what they were before, which is the correct outcome, not a miss.