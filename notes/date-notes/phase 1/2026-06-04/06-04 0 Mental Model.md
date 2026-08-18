## Plain-text Logs


A human-readable sentence:
```
2026-06-04 10:32:01 INFO Checked target 18 successfully in 153 ms
```

The problem isn't readability, it is that the meaning is embedded in the words rather than in fields. Consider wanting to search for something like `target 18` you would do `grep "target 18"` but this only really works if every log line keeps the same structure. The moment any uses something like `checked target 18` and another uses something like `check completed for endpoint id =18` Then we have two different search patterns for the same event, `target 18` vs `endpoint id = 18`. And searching blindly is called "grep-and-guess". Instead of querying for a field, you query for a word and hope you don't get the wrong thing, and / or miss out on the right things.


## Structured Logs Vs. structured JSON logs

These are two layers not really the same thing. Each value gets a name instead of being within in a sentence

```
event: check_completed
target_id: 18
latency_ms: 153
```


JSON is just a serialization format many many many tools use and expect (`jq`, Loki, Datadog):

```JSON
{
"event": "check_completed"
"target_id": 18
"latency_ms": 153
}
```


## Correlation ID

One ID generated per request, that is connected to every log line for which that request produces as it flows through validation, the database call, the redis write, the response. This is useful since then when we have many logs we can see which ones are connected to which requests. Using a shared `correlation_id` field you can filter to a single value and get a requests entire story in order, even if other logs are interwoven.


A distinction must be made between a `correlation_id` and a `target_id`. The first answers "which request produced these logs" whereas the other says "which monitored target was involved". A single request is connected to a single target, but that same target is touched by many different requests, each with their own logs.

### `correlation_id` vs. `execution_id`

we define `correlation_id` narrowly. A correlation id connects incoming requests (where our APP is the server) to every log line produced. It is a request scoped. It exists solely because a **client** called our API.

Our `perform_check` scheduler runs are in fact the opposite. Nothing external called them. `APScheduler` decided it was time to execute. There is no request to correlate to, so using a `correlation_id` is a bit weird. Instead we use a different id with a different name to make a distinction between the two, i.e. `execution_id`, generated at the start of each scheduler run, and attached to it is every log line the run produces.

|                            | `correlation_id`                                           | `execution_id`                                                                                        |
| -------------------------- | ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Who initiated the work** | An external client, using the server side of your app      | Your own process, using the client side of your app, such as calling another endpoint through `httpx` |
| **Trigger**                | An inbound HTTP request                                    | An APScheduler tick or other self-triggered background work                                           |
| **Generated where**        | FastAPI middleware, when request handling begins           | At the top of `perform_check`, when one check run begins                                              |
| **What it groups**         | Logs produced while handling one API request               | Logs produced during one specific check execution                                                     |
| **Example log line**       | `{"event":"request_completed","correlation_id":"req-123"}` | `{"event":"http_completed","execution_id":"run-456","target_id":18}`_                                 |


## rewrite

**The alternatives**

- **Plain logs** — what you have by default. Fine for one developer reading one terminal at a time; breaks down once you need to filter, aggregate, or trace concurrent activity.
- **OpenTelemetry tracing** — a step beyond correlation IDs. Instead of a flat shared id on log lines, it builds an actual tree of timed "spans" (HTTP request → DB query → Redis call, each with duration and parent/child relationships), which you'd visualize as a waterfall diagram in a backend like Jaeger or Tempo. More precise about _where time went_ across components, but it requires instrumentation, context propagation, exporters, and a tracing backend to view any of it. A correlation id is something your app just generates and stamps on logs; a trace id is part of that whole standardized system. Real value later, not needed for a single local process today.
- **Hosted logging** — Datadog, Splunk, CloudWatch, etc. Instead of you running `docker compose logs app | jq` by hand, your logs ship to an external platform that gives you search, dashboards, retention, and alerting across many machines. Useful once you're running in more than one place; for now it'd just add an account, credentials, and another tool to configure and explain for no real benefit, since you're the only consumer of these logs and they're all on one machine.

The layering, worth keeping as a mental model: your app emits events → plain text or JSON determines their shape → Docker captures stdout locally (that's as far as you're going today) → a hosted system could ingest them later if the shape is already clean. Tracing and metrics are parallel concerns answering different questions ("where did time go" and "how often does this happen system-wide," respectively), not competing choices for the same job as logs.