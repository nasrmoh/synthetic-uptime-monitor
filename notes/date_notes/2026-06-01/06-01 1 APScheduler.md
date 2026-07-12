
## Version Trap

APScheduler 3.x and 4.x have different APIs:
- Check which version is installed, and pin it explicitly in `requirements.txt`



## Correct FastAPI Integration Pattern

Scheduler starts and stops with the app via `lifespan`


```python
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler


scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
	scheduler.start()
	yield
	scheduler.shutdown()

app = FastAPI(lifespan=lifespan)
```





## Four Components

- Trigger: The timing logic (`date` = once, `interval` = fixed gap, `cron` = calendar time)
- Job Store: holds job definitions (what to run and when). Default is in-memory, so lost on restart. 
- Executor: Actually runs the jobs when it's due generally via a thread pool. The scheduler decides when, the executor performs the call
- Scheduler: Binds the above together and is the object we interact with to add/modify/remove jobs. Usually only one per app



## Adding Jobs: Two approaches

- `scheduler.add_job(...)`: Dynamic, added at runtime.  We use this as our jobs depend on `EndpointTarget` which aren't fixed
- `@scheduler.schedule_job(...)` decorator. For schedules fixed at code-time. 


## Concurrency Settings We'll Use


`max_instances` we will set to 1. 
`misfire_grace_time` is how long a missed run can be ran after it has missed its correct time and still run. Past this time it will be discard
`coalesce` this collapses multiple missed runs into one single run. 


## Implementation Details

- One scheduler inside of FastAPI
- `max_instances=1` per target job
- HTTP timeout shorter than check interval
- `coalesce=True`
- Results should be committed to postgres immediately. 
