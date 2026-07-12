## `APScheduler`

A library that decides when a function runs. Doesn't do any work itself, it calls the a function (say our checker function) on some trigger (timer interval, cron (time based), one-off). Splits the responsibility. Our checker function defines what happens, but `APScheduler` defines when it happens


## A "job"

A registered "unit" of work. Includes a function, its arguments, its trigger, and its concurrency rules (`max_instances`, `coalesce`, `misfire_grace_time`). This isn't a separate process, only a scheduled function call. In our app, a job is something simple like "run the checker for target 43 every 40 seconds"


## Concurrency

This is multiple tasks in progress during overlapping time windows, but it doesn't necessarily mean they execute at the same exact time (that's parallelism). This is relevant because HTTP checks usually spend most of their time waiting on the network. So while target `A`'s request is in flight, the scheduler can start target `B`'s check or the app can handle incoming `/targets` requests. If we didn't have concurrency everything would be blocked behind everything else. (Can't start anything until A is exactly finished)


## Workers and App Lifecycle

A worker executes a unit of work. As of right now, "worker" refers to a thread inside of our FastAPI processes' thread pool. It is not a separate process. Some alternative architectures put workers in their own processes isolated from the API. We aren't doing that. This means that APScheduler shares  the same process memory, environment variables and crash fate as our FastAPI application. No in-memory state (job state, partial results) survives a crash. This is why we want to immediately write to Postgres instead of holding anything in memory


## The Interval Problem


Say we start a check every 5 seconds, but a given check takes 10s to complete then once the next check is about to start (at t=5s) the previous check is still resolving. Three parameters decide what should happen next:

- `max_instances`: This determines the number of the *same jobs* that can run at once. 
	- Default 1 means that at `t=5s` the second is blocked while the first is still resolving
- `coalesce`: If we missed some scheduled runs (checks) as we were busy resolving others, either run them all when free as a single job (coalesce set to on) or resolve the backlog (complete each separately)
- `misfire_grace_time`: How late a run is allowed to start before APScheduler gives up on it. 

With these 3 parameters we have the following three outcomes

- Overlap: Multiples copies of one job run at once (`max_instances` > 1).
	- Risk: Duplicate outbound requests, duplicate DB writes, Race conditions
- Skip: Run is blocked or discarded because a limit was hit. 
- Backlog: Missed runs pile up and fire in a burst once the scheduler catches up
	- Risk: A burst of stale checks and a resource spike right when the system is recovering


Practical Guardrail: Keep `HTTP timeout < check interval`. This means that requests that take too long should timeout before we create a new request. This prevents the overlap/skip/backlog question we need to answer for the jobs


