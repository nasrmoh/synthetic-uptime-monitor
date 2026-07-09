Writing out the Raw SQL just to get an idea of what is happening





should know what the shape of the `endpoint_target` table looks like again.

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
## `POST /targets` create a new target

```sql
INSERT INTO endpoint_targets (url, method, interval_seconds, timeout_seconds, failure_threshold, expected_status)
VALUES (:url, :method, :interval_seconds, :timeout_seconds, :failure_threshold, :expected_status);
```
- we don't include `id` because the server will handle setting it. 
- we don't include `created_at` because the server automatically assigns it at insertion time
- we don't include `enabled` since we decided to have endpoints automatically on by default



## `GET /targets` get all rows

```
SELECT id, url, method, timeout_seconds, interval_seconds, failure_threshold, expected_status, enabled
FROM endpoint_targets;
```

> Note we explicitly name the columns so that if we ever include a new column we don't really want to display our API doesn't leak it with `SELECT *`

## `GET /targets/{target_id}` get a single target

```
SELECT *
FROM endpoint_targets
WHERE id = :id;
```

>If id isn't found we get zero rows back instead of an error. So will need to handle the empty case and convert that into a 404. SQLAlchemy doesn't raise exceptions for missing rows


## `PATCH /targets/{target_id}`


```SQL
UPDATE endpoint_target
SET <<field_0>> = :<<field_0>>, <<field_1>> = :<<field_1>>, 
WHERE id=:id
```
- the fields we can change are `url`, `method`, `interval_seconds`, `timeout_seconds`, `failure_threshold`, `expected_status`, `enabled`.
- the fields we can't change are `id` (primary key), `created_at` (server controlled), `updated_at`(server managed)

In the Pydantic schema every patchable field is typed as `field: type | None = None` to make it optional. The `None` default just tells Pydantic not to require it, it doesn't mean the field is nullable in the database.

We'll use `model_fields_set` to get the fields the client has sent. Those are the ones we include in the `SET`. SQLAlchemy handles generating the dynamic `UPDATE` from the attributes we set on the modal instance before committing. 



## Delete / Disable Debate

If we delete endpoint targets from their table in the database we would have to go into the `check_result` and *cascade* the delete. Since we want to have a history its probably a better idea to just keep the data inside of the `check_result` table and only disable endpoint targets. That if there is an issue with an endpoint, we disable it and keep a record of what happened

```SQL
UPDATE endpoint_target
SET enabled = false
WHERE id=:id;
```



