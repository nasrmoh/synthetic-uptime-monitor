

**Consecutive failures — Option A vs Option B**

It's a good idea to keep track of the number of consecutive failures for a given endpoint. We have two main options for getting this information.

**Option A: query + Python loop**

The first option is to query the database for a given endpoint's consecutive number of failures. This can be done solely via SQL, but we don't really know how to do this. Generally for complicated things in SQL we would usually just use a simple query and then pass the data into Python, whose functionality is a bit less esoteric. Though this is a bit of a "using a hammer and seeing everything as a nail" sort of situation. It would work.

We would query for N number of results, say 60, ordered in descending order. Use a Python loop where if the most recent result is a success we set the count to 0, otherwise count until we hit another success or we hit the limit. This is limited in that if the number of consecutive failures is bigger than our cap, our value is inaccurate. If we choose a bigger limit, more data must be processed. And reading this information constantly means paying this price constantly, on every read.

**Option B: `current_failed_checks` column**

The other option is keeping a running count of the number of failures for an endpoint target on the endpoint target itself. We would just need to write to the table on every check. Reading it back later is a plain `SELECT` on `EndpointTarget`, no scan required. We suspect we'll be reading this value more often than we write it (dashboards, alert rules, status checks), so pushing the cost onto the write side is the better tradeoff.

**Decision: Option B**

**Where the write happens**

Both writes, the `CheckResult` insert and the `EndpointTarget.current_failed_checks` update, happen in `record_check_result`, in the same transaction. The value to write is derived from `current_failed_checks` already fetched earlier in `perform_check`, passed through rather than re-queried, since `perform_check` already has the `EndpointTarget` row loaded.

**Race condition discussion (why it doesn't apply here)**

There is a potential issue with concurrency. If we had two jobs for the same endpoint target both reading the same value, the final result depends on who finishes first and what result they get, giving several different possible outcomes.

Assuming two jobs where the current number of consecutive failures is 10:

- **Both fail.** Both read 10, both write 11 (overwriting each other). The correct value should be 12. This is a lost update, one of the two failures is silently dropped.
- **Both succeed.** Both read 10, both write 0. This happens to still be correct.
- **One fails, one succeeds.** Both read 10. If the failure finishes first, its write of 11 gets overwritten by the success's write of 0. If the success finishes first, its write of 0 gets overwritten by the failure's write of 11. The true value should be 0 or 1 depending on which check actually started first, but whichever job happens to _finish_ last wins regardless of correctness. The success-overwritten-by-11 outcome is the more dangerous of the two, since it makes an ongoing failure streak look worse than it is; the failure-overwritten-by-0 outcome is dangerous in the opposite way, since it silently hides that the endpoint is still failing.

All of this is prevented by the fact that we have a guard in place: `max_instances=1` is set per-job whenever check-result jobs are created, and each endpoint target has its own dedicated job. This guarantees two checks for the _same_ target can never run concurrently, so the read-then-write here is safe in practice, even though the pattern itself is not inherently safe.
