
# Failure Analysis: Bad Target to Alert, End to End

**Drill:** Register a target that always fails, then trace the full path from a persisted check result to an alert landing in Alertmanager.

**Target under test:** `target_id=19`, failing with `ConnectError` (connection refused, no response received).

---

## Chain of evidence

We verified each link in order rather than checking only the final alert, so that a break would tell us _where_ the path failed rather than just _that_ it failed.

### 1. PostgreSQL: the check result persists

```
  id   | status_code | error_class  | target_id |         checked_at         | latency_ms
-------+-------------+--------------+-----------+----------------------------+------------
 13193 |             | ConnectError |        19 | 2026-08-07 07:11:00.534961 |         53
```

`status_code` is null and `error_class` is set, which is what our error-vs-failure taxonomy predicts: no response was received, so there is no status code to record. A status mismatch would produce the inverse (status code present, `error_class` null).

### 2. Redis: last-status cache reflects the same result

```json
{
  "status_code": null,
  "error_class": "ConnectError",
  "latency_ms": 53,
  "checked_at": "2026-08-07T07:11:00.604594"
}
```

The cache agrees with the durable row. Redis is written after Postgres, which is visible in the ~70ms gap between the two `checked_at` values.

### 3. `/metrics`: the counter increments

Value moved from 7.0 to 8.0 on this check:

```
checks_total{error_class="ConnectError",status="error",target_id="19"} 8.0
```

The metric label set matches the DB row, so instrumentation and persistence agree on the classification.

### 4. Prometheus: the scrape lands

Same series, observed through the Prometheus UI:

```
2026-08-07T07:12:50Z
checks_total: 8
error_class: ConnectError
instance: app:8000
job: synthetic-uptime-monitor
status: error
target_id: 19
```

The timestamp lag against the DB row is scrape interval plus evaluation delay, roughly 20 seconds here. Prometheus does not see a value the instant it changes; it sees it on the next scrape.

### 5. Prometheus: the rule fires

From `localhost:9090/alerts`:

|Alert labels|State|Active Since|Value|
|---|---|---|---|
|`alertname="TargetDown"`, `error_class="ConnectError"`, `instance="app:8000"`, `job="synthetic-uptime-monitor"`, `severity="critical"`, `status="error"`, `target_id="19"`|firing|9m 49.761s|5.342584314884796|

### 6. Alertmanager: the alert is received

```
2026-08-07T07:08:13.599Z
alertname="TargetDown"
error_class="ConnectError"
instance="app:8000"
job="synthetic-uptime-monitor"
severity="critical"
status="error"
target_id="19"
```

---

## Timeline

|Event|Time|Source|
|---|---|---|
|Alertmanager first received the alert|07:08:13.599Z|Alertmanager UI|
|Check result persisted|07:11:00.534961|`check_results` id 13193|
|Redis cache updated|07:11:00.604594|`redis-cli`|
|Prometheus observed the incremented counter|07:12:50Z|Prometheus UI|

**To complete:** predicted versus actual timings for first failure to `PENDING` to `FIRING`, derived from `interval_seconds`, the 15s scrape interval, the rule evaluation interval, and the rule's `for:` duration. Also the arithmetic on Active Since (9m49s) against the Alertmanager first-received timestamp, which mark different events and should differ by roughly `for:`.

---

## After we fix it

We changed the URL for target 19 so the check now succeeds.

**PostgreSQL:**

```
13260 |         200 |              |        19 | 2026-08-07 07:33:00.533683 |        246
```

**Redis:**

```json
{
  "status_code": 200,
  "error_class": null,
  "latency_ms": 246,
  "checked_at": "2026-08-07T07:33:00.787439"
}
```

**`/metrics`:**

```
checks_total{error_class="none",status="success",target_id="19"}
```


**Prometheus scrape, via UI:**

```
2026-08-07T07:33:37Z
checks_total: 1
error_class: none
instance: app:8000
job: synthetic-uptime-monitor
status: success
target_id: 19
```

`checks_total` starts at 1, not continuing from wherever the error series left off. This is the labels-as-identity point from the dedup section showing up again, but on the metric side rather than the alert side. `error_class="ConnectError"` and `error_class="none"` are different label combinations, so they are different time series to Prometheus. The success series is brand new; the error series is still sitting at whatever value it last held, just no longer being incremented.

**Prometheus `/alerts`:**

`uptime-monitor-alerts` / `/etc/prometheus/rules/alerts.yml`, `TargetDown` is now **inactive (1)**.

```
TargetDown
increase(checks_total{status="error"}[5m]) > 2
for: 1m
severity="critical"
summary: Target {{ $labels.target_id }} has failed repeatedly in the last 5 minutes
```

**Alertmanager:** no alert groups found.

**Update, from the webhook receiver:** the resolved notification arrived.

```json
{"receiver":"default","status":"resolved","alerts":[{"status":"resolved","labels":{"alertname":"TargetDown","error_class":"ConnectError","instance":"app:8000","job":"synthetic-uptime-monitor","severity":"critical","status":"error","target_id":"19"},"annotations":{"summary":"Target 19 has failed repeatedly in the last 5 minutes"},"startsAt":"2026-08-07T07:08:13.599Z","endsAt":"2026-08-07T07:36:13.599Z","generatorURL":"http://d19b72dd0e74:9090/graph?g0.expr=increase%28checks_total%7Bstatus%3D%22error%22%7D%5B5m%5D%29+%3E+2\u0026g0.tab=1","fingerprint":"1c90b4a513296c21"}],"notification_reason":"all alerts resolved","groupLabels":{},"commonLabels":{"alertname":"TargetDown","error_class":"ConnectError","instance":"app:8000","job":"synthetic-uptime-monitor","severity":"critical","status":"error","target_id":"19"},"commonAnnotations":{"summary":"Target 19 has failed repeatedly in the last 5 minutes"},"externalURL":"http://d52214f6e7d0:9093","version":"4","groupKey":"{}:{}","truncatedAlerts":0}
```

**`startsAt` matches the original Alertmanager first-received timestamp exactly (07:08:13.599Z), same `fingerprint` throughout.** Second confirmation of the dedup finding above: Alertmanager tracked this as one continuous alert object from first arrival to resolution, never opening a new entry for any of the intermediate resends.
