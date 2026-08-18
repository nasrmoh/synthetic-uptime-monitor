# What is the Persistence Service?

This is a function that other places in our code will be using.

## Why a function instead of a route? 

Because of the caller of it. The intention is to have a scheduler which lives inside of the app run this function. Since the scheduler is part of the app there isn't any need for it to make an HTTP request, as it can call the Python function directly. Then our "insert a check result into the database" ought to be a function that anything in our codebase (like the scheduler) can call. 

```python
def record_check_result(db, target_id, status_code, latency, error_class...):
	# Build a check result object
	# add it to the session
	# commit
	# return
```

## But Wait What Is The Scheduler?

The scheduler is APScheduler, a library that's inside the FastAPI app. It fires a function on a timer. Acting as a background job runner. We hand it a function and an interval (say every 2 minutes) and it will automatically call the associated function. 


## Do We Need Pydantic For This Part?

For the persistence function we won't need it. This is because it takes in Python values (int, str, etc.) and returns `CheckResult` (SQLAlchemy ORM Object). So Pydantic isn't necessary. We only use Pydantic if we expose something over HTTP, as Pydantic's job is to validate and shape the incoming data through a request body or out through a response. 


