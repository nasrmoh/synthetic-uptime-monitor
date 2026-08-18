


Certain parts of the scheduler system (which?) require a dependency (access to the database) 

our function `get_db` is a generator function 

```python
def get_db():
	db = SessionLocal()
	try:
		yield db
	finally:
		db.close()
```

Within our route functions we accomplish dependency injection via FastAPI's pattern

`def route_fn(db : Session = Depends(get_db))`

Which lets FastAPI handle the process of setting up and tearing down the dependency. But the functions  our scheduler uses do not have these setup. They aren't connected to FastAPI's system. 


possible solutions.

Use `next()` twice to get back a `Session` object. First `next()` yields our Session object. Second `next()` tears it down
- works but leads to a `StopIteration` exception. 
	- Catch the exception within `get_db()` ? 
		- Could work but not a good reason to change the structure of our function


use the decorator `@contextmanager` from context lib so we can do

``` python
with get_db() as db:
	...
```

Works for our scheduler functions :) but... it messes up how FastAPI handles dependencies

Solution. create a new function `get_db_with_context()` that just returns `get_db()` with the decorator

```
@contextmanager
def get_db_with_context():
	return get_db()
```

And whenever we need to database dependency but somewhere FastAPI isn't handling it we use this function instead.




