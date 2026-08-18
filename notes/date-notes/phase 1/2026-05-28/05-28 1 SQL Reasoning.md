> 🗄️ SQL REASONING In `notes/sql/2026-05-28-timeseries.md`, write the recent-results query pattern and explain why result history belongs in its own table rather than as JSON inside the target row — one sentence on why time-series-like data is separated.

## Recent Results Query

```sql
SELECT *
FROM check_result
WHERE target_id=:target_id
ORDER BY checked_at DESC
LIMIT :limit;
```

My original reasoning for not including check results as JSON within endpoint target is that simple questions like "how many results do we have?" would need to go through the endpoint target table.

Say check results existed as entries in a JSON object on the endpoint target row. The main issue is that whenever we want to add a new check result, PostgreSQL will not "append" the new value, instead it has to rewrite the entire row!!! Imagine an endpoint target that's been running for a year, creating a new check every 30 seconds, that's about 1 million values in a JSON object. If we wanted to add 1 more result, PostgreSQL would need to rewrite a row containing all 1 million existing values just to add the millionth-and-first.

Expanding on "having to go through endpoints to get data about checks": if we wanted to count the number of checks, we'd need to pull every target's JSON object into memory and count entries inside each one ourselves. With a real table, `SELECT COUNT(*) FROM check_results` does this in a single fast operation, no unpacking required.

# Why Time-Series-Like Data is Separated.

Different rates of change
- `endpoint_target` values are rarely being changed, and when they do change its by human input. `check_result` rows are created constantly. And once they are written they aren't supposed to be edited. And `endpoint_target` usually has a finite size, whereas `check_result` can grow forever
	- one table has values that are human made and human edited, finite size
	- one table is machine made and not supposed to be edited, unbounded

Query Shape
- The queries we make are easier with different "data shapes":
	- *Recent results for one target*: 
		- Slice a single targets results by time 
	- *Failures for one target*
		- aggregate within a single target 
	- *Which targets are failing, system wide* 
		- aggregate across all targets, grouped by target.
	- *Read or edit a config*
		- want to edit a endpoint target and we don't care about the results associated to it

These different queries become awkward if we have a single table. In other words, give the database rows (create a table for the data), not nested values (don't place complex data inside of already existing table), if we intend on querying that complex data. 







