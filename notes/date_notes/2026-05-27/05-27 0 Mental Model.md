# FastAPI Request Body + Path Parameters

Sending data from a client to our API is done via a **request body**, whereas a **response body** is the data sent back from our API to the client.
- clients don't always need to send a request body, but we almost always want to send a response body to the client

>Almost always data is sent using the HTTP methods **POST**, **PUT**, **DELETE** or **PATCH**


## Importing the Base Model

```python
from pydantic import BaseModel
```

- Our request bodies inherit from `BaseModel` that gives us access to validation


## Creating The Data Model

``` python
class Item(BaseModel):
	name: str
	description: str | None = None
	price: float
	tax: float | None = None
```
- each attribute becomes a field in the expected JSON body. The type annotation is what tells Pydantic what to validate against
	- fields with no default are required `name/price 
	- fields with default aren't required `description/tax`


the pattern `field: str| None = None` combines two things.
- the client can leave the field empty, i.e. omit it
- the client can include the value but just leave it `null` 

Both of these are valid
```json
{
	"name": "Keyboard"
}
{
	"name": "Keyboard",
	"description": null
}
```

> Useful for `PATCH` paths where an omitted field means "don't change this" versus an included field set to `null` means "change and make it null"


## Declaring it as a Parameter

```python
@app.post("/items/")
async def create_item(item: Item):
	...
```

FastAPI will do the following:
- See the Pydantic Model
- Read the request body as a JSON
- Validate each field
- Pass the resulting Object into the function


## Using the Model

Inside of the route request body is a normal Python object:
```python
item.name
item.tax
```


## Getting a Dictionary from our Request Body

using `.model_dump()` we can get a plain dictionary form of our request body
```python
item.model_dump()
# {"name": "Keyboard", "price": 59.99, "description": None, "tax": None}
```

## Combining Parameters

FastAPI determines automatically where each parameter comes from based on its type and where it appears in the path decorator

|Parameter type|Comes from|
|---|---|
|Appears in the route path (`/items/{id}`)|Path|
|Pydantic model|Request body|
|Simple type (`int`, `str`, `bool`) not in the path|Query string|
|Pydantic model with a default of `None`|Still request body, not query string|

### Path + Body

```python
@app.put("/items/{item_id}")
async def update_item(item_id: int,k item: Item):
	...
```
```
PUT /items/5
Body: {"name": "Keyboard", "price": 59.99}

item_id = 5       <- path
item = Item(...)  <- body
```
- we see that `item_id` is a path parameter, whereas `item` is a request body

### Path + Body + Query

```python
@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item, q: str | None = None):
	...
```
```
PUT /items/5?q=electronics
Body: {"name": "Keyboard", "price": 59.99}

item_id = 5          <- path
item = Item(...)     <- body
q = "electronics"   <- query string
```
- we see that `item_id` is a path parameter (in the path), `item` is a request Body based on its type, and since `q` isn't either its a query string.




