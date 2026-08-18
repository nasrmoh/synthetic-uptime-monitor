# What Validation is required for our Endpoint Target Attributes?

- `url`
	- Should be an actual URL
- `method`
	- Should be a valid HTTP method
> Can be done using an `ENUM`
- `timeout_seconds`
	- Should be a positive non-zero integer, smaller than `interval_seconds`
> Pydantic has something like this
- `interval_seconds`
	- Should be a positive non-zero integer
- `failure_threshold`
	- Should be positive integer
		- Since failure on a single check (threshold of 0) could be useful
- `expected_status` 
	- Should be a valid Status code as an integer
		- check integer is between (100-599)
			- maybe later check for only valid existing HTTP status codes?

# Pydantic Schemas

> Note that schemas can function as input or output but not both

We'll need 3 Schemas
- `TargetCreate`
	- The required fields to make a new target created by the client via `POST`
	- Input only, its the request body for `POST` 
- `TargetResponse`
	- The acquired fields when the client requests them via `GET`
	- This is our output field. 
- `TargetUpdate`
	- Same as `TargetCreate` but with optional fields. used for `PATCH`
	- Input only, its the request body for `PATCH`


## Why Target Response needs `from_attributes=True`

When a client hits a `GET` endpoint:
1. FastAPI receives the request and calls the route function
2. The route queries the database via SQLAlchemy
3. SQLAlchemy returns a Python object with attributes (`row.id`, `row.url`, `row.created_at`)
4. FastAPI hands that object to Pydantic to serialize into `TargetResponse`
5. Pydantic defaults to dictionary lookup -- `row["url"]` -- which fails because the SQLAlchemy object is not a dictionary, it has attributes
6. Setting `from_attributes=True` on `TargetResponse` tells Pydantic to look up attributes instead -- `row.url` -- which works because the attribute names match what SQLAlchemy returned
7. Pydantic builds the `TargetResponse`, FastAPI serializes it to JSON, and sends it back to the client
> "This is all necessary because `TargetResponse` involves converting a SQLAlchemy ORM object into JSON -- Python object to JSON -- and Pydantic needs `from_attributes=True` to read attributes off that object. `TargetCreate` and `TargetUpdate` only go in the other direction -- JSON to Python object -- where Pydantic reads a dictionary, which works by default."


