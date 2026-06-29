## Designing the Data Model

>What information does the monitor need?

When we send a request the monitor needs to know the following.
- The URL (endpoint) to send the request to
- The HTTP method (`GET`, `POST`, etc.).
- How often we should check the endpoint

Once a request is sent we need to keep track of the result. The HTTP status code.

Typical status code ranges are:
```
2xx   Success
3xx   Redirects
4xx   Client errors (bad request, unauthorized, not found)
5xx   Server errors (server failure)
```

Sometimes requests never receive a response, if such a request takes too long, we consider it *timed out*. So our monitor needs to know how long it should wait before treating the request as a failure.

A small failure, or really a small number of failures are normal. Failures like these shouldn't mark a service as being down, so the monitor should know how many consecutive failures it records before it declares a service as being down.

In certain circumstances, say in the case of maintenance, we might want not monitor an endpoint as being down. So the monitor needs to know whether or not an endpoint is "enabled" that is ready to be checked against.

Besides these specific fields we need fields to keep track of extra information:
- A primary key `id`
- when an endpoint target was made `created_at`
- when an endpoint target was last updated `updated_at`


## `EndpointTarget`

Stores the configuration details for every endpoint we want to monitor

| **Field**           | **Purpose**                                                                                                                                                             |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                | Identifier for the endpoint.                                                                                                                                            |
| `url`               | The endpoint that will receive HTTP requests.                                                                                                                           |
| `method`            | The HTTP method (`GET`, `POST`, etc.) used when checking the endpoint.                                                                                                  |
| `interval_seconds`  | How often the endpoint should be checked.                                                                                                                               |
| `timeout_seconds`   | How long to wait before considering the request to have timed out.                                                                                                      |
| `failure_threshold` | Number of consecutive failed checks before the endpoint is considered down.                                                                                             |
| `expected_status`   | The HTTP status code considered to represent a healthy response. This allows endpoints that intentionally return codes other than `200` to still be considered healthy. |
| `enabled`           | Indicates whether this endpoint should currently be monitored.                                                                                                          |
| `created_at`        | When the endpoint configuration was created.                                                                                                                            |
| `updated_at`        | When the endpoint configuration was last modified.                                                                                                                      |

## `CheckResult`

Stores the outcome of every single health check performed by the monitor, with each row being its own observation.

| **Field**     | **Purpose**                                                                                                                       |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| `id`          | Unique identifier for the observation.                                                                                            |
| `target_id`   | Foreign key linking the result back to the `EndpointTarget` that generated it.                                                    |
| `status_code` | The HTTP status code returned by the endpoint, if a response was received.                                                        |
| `latency_ms`  | Time between sending the request and receiving the response, measured in milliseconds.                                            |
| `error_class` | The type of failure encountered (for example, timeout or DNS resolution failure). This field is `NULL` when the request succeeds. |
| `checked_at`  | Timestamp indicating when the check was performed.                                                                                |
We can use multiple observations from `CheckResult` to calculate things like
- Uptime percentage
- Outage duration
- Latency.



SQL

``` SQL
CREATE TABLE endpoint_targets(
	id SERIAL PRIMARY KEY,
	url TEXT NOT NULL,
	method TEXT NOT NULL,
	interval_seconds INTEGER NOT NULL,
	timeout_seconds INTEGER NOT NULL,
	failure_threshold INTEGER NOT NULL,
	expected_status INTEGER NOT NULL,
	enabled BOOLEAN NOT NULL default true,
	created_at TIMESTAMPTZ NOT NULL default now(),
	updated_at TIMESTAMPTZ 
);
```


```sql
CREATE TABLE check_results(
	id SERIAL PRIMARY KEY,
	status_code INTEGER NOT NULL,
	error_class TEXT,
	target_id INTEGER NOT NULL REFERENCES endpoint_targets(id),
	checked_at TIMESTAMPTZ NOT NULL default now(),
	latency_ms INTEGER NOT NULL
)
```


Finally we'll need something for indexing. We'll use the endpoint target and order the results by when they were checked at

```sql
CREATE INDEX index_target_checked_time
ON check_results(target_id, checked_at DESC);
```


## Basic Queries

### Insert a new target
```SQL
INSERT INTO endpoint_targets(url, method, interval_seconds, timeout_seconds, failure_threshold, expected_status)
VALUES ('/health', 'GET', 60, 120, 30, 200)
```

### List all active targets
```sql
SELECT *
FROM endpoint_targets
WHERE enabled = true;
```

### Fetch One Target by ID
```sql
SELECT *
FROM endpoint_targets
WHERE id = x;
```


### Insert a check result

```sql
INSERT INTO check_results(status_code, target_id, latency)
VALUES (200, 20, 500);
```


### Fetch Recent Results for one Target

```sql
SELECT *
FROM check_results
WHERE target_id = 3
ORDER BY checked_at DESC
LIMIT 10;
```


## Index Reasoning

We index by `(target_id, checked_at DESC)` instead of just using `target_id` alone because our most common query is one where we get the most recent results for a particular endpoint. Using an index like this allows PostgreSQL to very quickly locate the rows for a specific target while ensuring that PostgreSQL doesn't have to sort. 

## Timestamp Reasoning

We use `TIMESTAMPTZ` instead of `TIMESTAMP` so that the time values can be consistent regardless of where the machine collecting the data is located within. 