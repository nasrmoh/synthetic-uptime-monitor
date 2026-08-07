# Alert Rule Reasoning — TargetDown

## Adding `target_id` as a label

For our Prometheus metric `checks_total`, we want to be able to see which
target is "down." We currently label it with `status` and `error_class`;
we're adding `target_id` so the metric can tell us *which* target is
failing, not just that *something* is.

With `target_id` on the alert, a quick script can take that ID and query
our own API for more detail. We built this as an HTTP request against
`/targets/{target_id}` (could go via a direct SQL query instead, but our
existing scripts all go over HTTP, so this stays consistent with that
pattern) rather than a raw Postgres query.

### Cardinality tradeoff

Adding `target_id` is a real cardinality cost: `target_id` is unbounded,
so the number of distinct time series Prometheus has to track grows
linearly with target count (multiplied by `status` × `error_class`
combinations). This doesn't scale to production levels, but since this
is an MVP and we don't expect more than 10-20 targets, the cost is
negligible in practice. Documented as a known, deliberate tradeoff rather
than an oversight, revisit if target count ever grows into the hundreds
or thousands.

> ⚠️ TODO: add a constraint to prevent invalid/unexpected values from
> being inserted into target data, need to define exactly what that
> constraint is (this note was left unfinished, follow up before Jun 15).

## The rule

```yaml
groups:
  - name: uptime-monitor-alerts
    rules:
      - alert: TargetDown
        expr: increase(checks_total{status="error"}[5m]) > 2
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Target {{ $labels.target_id }} logged more than 2 failed checks in the last 5 minutes"
```

`TargetDown` fires when `increase(checks_total{status="error"}[5m]) > 2`,
more than 2 failed checks out of a possible ~5 (at a 60s check interval)
within a 5-minute window.

This measures the *total* number of errors in the window, not
*consecutive* errors. It can't distinguish 3 errors in a row from 3
scattered errors with successes in between, both trip the same
threshold. A gauge-based metric (e.g. exposing our existing
`current_failed_checks` value) would resolve this by resetting to zero
on any success, giving a true "consecutive failures" signal. Deferred to
Phase 2: requires a new metric and new call sites, not justified for
today's MVP scope.