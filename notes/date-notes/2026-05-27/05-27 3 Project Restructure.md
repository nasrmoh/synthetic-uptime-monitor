
We split our old project from just using `main.py` and `db.py` with main having our pydantic  models and routes into the following
```
/app
	main.py
	db.py
	models.py
	schemas.py
	/routers
		targets.py
```

To get `main.py` wired to talk to `target.py` we use FastAPI's provided functionality via `app.include_router(targets.router, prefix=<<route>>)`

For example

``` python
from fastapi import FastAPI
from app.routers import targets

app = FastAPI()

app.include_router(targets.router, prefix="/targets")
```


And within `routers/target.py` we link back like this

```python
from fastapi import APIRouter
router = APIRouter()

# Our routes go here
# @router.get("/")
# note that we now do @router instead of @app
```


