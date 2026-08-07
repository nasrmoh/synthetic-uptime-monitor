## What Is an Alert?

An alert is the result of a Prometheus alerting rule expression evaluating to true.

For example:

```yaml
- alert: TargetDown
  expr: up == 0
  for: 1m
```

On each evaluation interval, Prometheus checks whether `up == 0` is currently true.

When the expression first becomes true, Prometheus creates an alert instance internally. That instance contains:
- an alert name, such as `TargetDown`
- labels copied from the underlying time series, such as `instance="app:8000"`
- a state
- the time the condition started

Alerts move through three states:

1. **Inactive** — the expression is false.
2. **Pending** — the expression is true, but hasn't remained true for the full `for` duration yet.
3. **Firing** — the expression has remained true for the required duration.

The alert still isn't a "notification" at this point, it's just an internal object Prometheus is tracking: "this condition is currently true, and has been true since this time."

You can check alert instances on Prometheus's `/alerts` endpoint even if Alertmanager isn't running. This makes it clear that alert *evaluation* and alert *delivery* aren't the same thing.

## Is Alertmanager Separate from Prometheus?

Yes. It's its own program, its own process, its own Docker Compose service.

Prometheus and Alertmanager communicate over HTTP. Prometheus evaluates alerting rules and periodically sends its currently-firing alerts to Alertmanager's API. Alertmanager then applies its own notification policies on top of that.

If Alertmanager is unavailable:
- Prometheus keeps scraping metrics.
- Prometheus keeps evaluating rules.
- Alerts can still become pending or firing.
- Alerts remain visible on Prometheus's `/alerts` endpoint.
- Notifications simply aren't delivered to receivers.

## Our Alert Flow

1. FastAPI exposes metrics, e.g. the total checks counter.
2. Prometheus scrapes those metrics.
3. Prometheus evaluates an alerting rule using PromQL.
4. The alert moves from inactive to pending to firing.
5. Prometheus sends the firing alert to Alertmanager.
6. Alertmanager applies routing, grouping, deduplication, silencing, and inhibition.
7. Alertmanager sends a notification to a configured receiver.

A receiver could be:
- a webhook
- email
- Slack
- PagerDuty
- any other incident-management system

## What Alertmanager Handles

### Routing

Routing decides where an alert goes based on its labels. For example:


```
severity="warning" -> normal webhook  
severity="critical" -> PagerDuty  
team="database" -> database team
```


Alertmanager reads those labels and selects the appropriate receiver. This means notification destinations can change without touching the PromQL rule that detects the problem.

### Grouping

Grouping combines related alerts into a single notification. Say 100 monitored targets fail at once because of a network outage. Without grouping, that's 100 separate notifications. Alertmanager can group them into one notification covering all affected targets.

### Deduplication

Prometheus doesn't send an alert to Alertmanager once and forget it. While an alert remains firing, Prometheus keeps resending its current active-alert state. Without deduplication, every resend would produce another Slack message or webhook request.

Alertmanager uses an alert's labels as its identity. When a new alert arrives with the same labels, it updates the existing alert rather than treating it as a new incident. The result is one ongoing incident instead of repeated notifications.

### Silencing

Silences temporarily prevent matching alerts from producing notifications. For example, if you're taking Postgres down for planned maintenance, you can silence alerts matching `service="postgres"`.

The alert can still be evaluated by Prometheus, still fire, and still be received by Alertmanager, it just won't produce a notification while the silence is active.

### Inhibition

Inhibition suppresses secondary alerts when a more important, related alert is already firing.

For example:
- `ServerDown` is firing
- `APIUnavailable` is firing
- `DatabaseConnectionFailed` is firing

If the entire server is down, the API and database alerts are likely just symptoms of that larger failure. An inhibition rule can suppress `APIUnavailable` and `DatabaseConnectionFailed` while `ServerDown` is active, cutting the noise down to one meaningful signal.

Unlike silencing, inhibition depends on another alert being active, it's not a manual, time-boxed suppression.

## Why Metric Evaluation and Delivery Policy Are Separate

Prometheus and Alertmanager are separate services because they solve different problems.

Prometheus handles metric collection and alert evaluation:
- scrape targets
- store time-series data
- evaluate PromQL
- determine whether an alert condition is true
- track inactive, pending, and firing states

Alertmanager handles delivery policy:
- decide who should receive an alert
- choose the delivery channel
- group related alerts
- remove duplicate notifications
- suppress alerts during maintenance
- suppress secondary symptoms

Metric evaluation is fundamentally a data and logic problem. Notification delivery is fundamentally a routing and human-response problem.

Prometheus determines:

> "The target has been down for one minute."

Alertmanager determines:

> "This is a critical production alert. Group it with related failures, and send it to the on-call receiver."

