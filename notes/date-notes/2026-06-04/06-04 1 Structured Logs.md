# structlog mental model — 2026-06-04

## The core object: event dict

To structlog, one log entry is just a dict. `log.info("check_completed", target_id=18)` builds `{"event": "check_completed", "target_id": 18}` — as a dict from the start, not a string that later gets converted. Everything else in the library exists to build, merge, transform, and render that dict. JSON is only the final serialization step at the end of the chain; the actual value is that the data is structured _throughout_, not that it happens to end up as JSON.

## Two ways context gets into the dict

- **`log.bind(key=value)`** — returns a _new_ logger carrying that context forward. Every call on that logger includes the bound fields without repeating them. Loggers are immutable — `bind()` doesn't mutate the original. Useful when a logger is already in hand and gets passed down through a function call chain (e.g. the checker function binding `target_id` onto its own local logger).
    
- **`contextvars.bind_contextvars(key=value)`** — thread/task-local storage, separate from any specific logger object. Anything logged anywhere during that unit of work picks the value up automatically, no logger threaded through function signatures. This is what solves concurrent FastAPI requests: two requests mid-flight with interleaved logs, and a plain global variable would let Request B overwrite the value while Request A is still logging, leaking B's id into A's lines. `contextvars` keeps each request's bound value isolated to its own execution context — Request A's logs always see `req-123`, Request B's always see `req-456`, regardless of interleaving. Requires `structlog.contextvars.merge_contextvars` in the processor chain, or none of it reaches output.
    

Context vars merge in first, then whatever's bound directly to the logger merges in on top of the event kwargs.

## Processor chain

A processor is `(logger, method_name, event_dict) -> event_dict`. Runs in order, each can add/change/remove fields, passes the result to the next. Order is a strict dependency, not a preference: each processor can only see fields added by processors that ran before it, and once the renderer runs, the dict stops being a dict — it becomes a string. `merge_contextvars` must run before the renderer, or bound context never reaches the final JSON (if the renderer ran first, `merge_contextvars` would receive a string with nothing left to merge into).

```
event_dict → merge_contextvars → add level → add timestamp → JSONRenderer → stdout
```

The renderer is the last processor in the chain — same shape as any other processor, except its output isn't another event dict, it's the final string.

## JSONRenderer

```python
structlog.configure(processors=[structlog.processors.JSONRenderer()])
log.info("hi")
```

```json
{"event": "request_completed", "correlation_id": "req-123", "method": "GET", "status_code": 200}
```

The renderer doesn't invent fields, it serializes whatever the chain already built.

## stdout → Docker

No log file needed. `application log call → event dict → processors → JSONRenderer → stdout → Docker captures the container's stdout → docker compose logs app`.

## Two flows for this project

**Inbound (`correlation_id`):**

```
middleware generates correlation_id → bind via contextvars → route/helpers log →
merge_contextvars adds it → level/timestamp added → JSONRenderer → stdout
```

**Outbound / self-triggered (`execution_id`):**

```
perform_check begins → bind execution_id (contextvars, or log.bind if it's a local
logger passed through the function) → checker logs each step → same processor
tail as above → stdout
```

Clear the bound context when the unit of work ends either way (request done, or `perform_check` returns), so nothing leaks into the next request or run.









