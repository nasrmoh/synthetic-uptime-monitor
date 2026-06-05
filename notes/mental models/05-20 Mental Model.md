# Intro Blurb
[[FastAPI]] is the HTTP boundary of this project: it turns incoming requests into Python function calls and serializes Python objects back into responses, using type hints to validate request/response shapes at the edge. It exists because Flask needs third-party libraries for validation and [[OpenAPI]] docs, while Django carries ORM/admin/template weight that a pure JSON [[API]] never uses. Without a framework, even `/health` and `/ready` would be repetitive socket-and-header plumbing before you reached any monitoring logic. It hides [[ASGI]] handling, [[request parsing]], [[dependency injection]], and [[schema generation]]. Real alternatives: Flask + Pydantic/Marshmallow, Starlette directly, Django REST Framework.


- What is [[FastAPI]]? 
- What is HTTP?
- What are requests?
- What are responses?
- What is flask?
- What is Django
- What is ORM
- What does this line refer to? "Django carries ORM/admin/template weight that a pure JSON [[API]] never uses. Without a framework, even `/health` and `/ready` would be repetitive socket-and-header plumbing before you reached any monitoring logic."
- What is [[ASGI]] handling?
- What is [[request parsing]]?
- What is [[dependency injection]]
- What is [[schema generation]]

# Notes

### The High Level Picture
a Web [[API]] is a program that:
- waits for network messages
- interprets them
- runs application logic
- and sends data back

The stack looks like this.
```
Internet
  ↓
HTTP
  ↓
Server
  ↓
[[ASGI]] interface
  ↓
FastAPI (routing, validation, serialization)
  ↓
Your logic
  ↓
Database / Redis / External APIs
```

So instead of doing:

```
raw_socket_bytes -> parse -> validate -> dispatch -> serialize
```

you write:
```python
@app.post("/metrics")
def ingest(metric : Metric):
	...
```


## What is HTTP?

HTTP (HyperText Transfer Protocol) is the agreed-upon rules for how a client and server talk over the web. Its based on a request / response protocol. The client sends exactly one single request, the server sends back exactly one single request. Its built on TCP which handles getting bytes from A to B. HTTP defines what those bytes *mean*

- In short HTTP is standardized system for programs to interact over the internet

HTTP defines:
- Methods
	- `GET`, `POST`, `PUT`, `DELETE`
- Headers
- Status Codes
- Body Formats

When the intro blurb is talking about "socket-and-header plumbing" it is referring to reading raw text from a socket and parsing them.

## What are Requests and Responses?

### Requests
A **request** is the message a client sends to ask for something. For example a browser fetching a page, a frontend asking for some JSON, a monitoring agent uploading metrics. 

Requests contain:
- Methods
- Paths
- Headers
- Metadata
	- Auth tokens
- and optionally a body


```http
POST /login
Authorization: Bearer abc123

{"username": "naz"}
```

### Responses

A **response** is the server's reply.

Responses contain:
- Status codes
	- 200 = success
	- 404 = not found
	- 500 = server error
- Headers
- and optionally a body

```http
200 ok

{"token": "xyz"}
```

## What is [[FastAPI]]?

[[FastAPI]] is a Python web framework for building APIs. Its asynchronous-first, strongly typed, designed around JSON APIs, and built on [[ASGI]]. Its core job:
- Turn incoming HTTP requests into Python function calls
- and turn what your functions return back into HTTP responses

```python
@app.get("/health")
def health_check():
	return {"status": "ok"}
```

when a request hits `/health`, [[FastAPI]] calls your function, serializes the returned dict to JSON and sends back a proper HTTP response with a 200 status. You never touch a socket or wrote a status line. 

**[[FastAPI]] is not your application logic. It is the layer around your logic**

It is the layer that handles repetitive infrastructure around that process so you can focus on the actual logic. Without a framework like [[FastAPI]] setting up an [[endpoint]] requires manually dealing with:
- Sockets
- HTTP message formatting
- Header and Body parsing
- URL routing
- JSON $\iff$ Python Conversions
- Validation
- Error formatting
- Concurrency
By using [[FastAPI]] you can abstract that all away


## What is Flask?

Flask is another, older and minimalist Python web framework. It handles
- routing
- request / response handling
Doesn't do much else. No validation, [[schema generation]], [[API]] docs, or ORM integration. So you end up having to use 3rd party libraries like (Marshmallow, `Pydantic`, `Flask-RESTX`, `SQLAlchemy`, etc.) [[FastAPI]] was partly a reaction to this separation. [[FastAPI]] combines these separate parts together.


## What is Django?

Django is another web framework albeit a **batteries included** one. Its designed for full server-rendered web applications. It includes:
- an ORM
- Authentication
- Admin Dashboard
- Templating Engine
- Migrations
- Sessions
- Forms

If you application simply receives and returns JSON, most of what Django provides is dead weight. A monitoring [[API]] doesn't need HTML templates or an Admin Dashboard so we end up with a Goldilocks problem. Django is heavy coming with lots of things out of the box (too hot) whereas using no framework is too lean (too cold). Something as simple as `/health` endpoint would require manual socket and header work before you can reach the actual logic. 


## What is an ORM

ORM (Object Relational Mapper). Instead of writing out SQL code, an ORM lets you handle database tables as if they were Python Objects.  So

```SQL
SELECT * FROM users WHERE id = 42;
```
Becomes:

```python
user = User.objects.get(id=42)
```
Benefits:
- Easy to use
- abstracts away SQL
Negatives:
- Hides away SQL behaviour
- Can make it easy to generate inefficient queries

ORMs are an abstraction layer over SQL making things more convenient, but aren't really a substitute for understanding some of how SQL works. 

## What is [[ASGI]]?

[[ASGI]] (Asynchronous Server Gateway Interface) is the standard interface between Python web applications and web servers. It defines how async python apps communicate with servers. [[ASGI]] is also the successor to the older synchronous standard WSGI

[[ASGI]] enables:
- async requests
- WebSockets
- Long lived connections
- High concurrency

for example. `Uvicorn` listens for HTTP requests, parses the traffic and converts requests into the [[ASGI]] format. Then it passes the request to the [[FastAPI]] application via [[ASGI]] interface. [[FastAPI]] handles routing and application logic, then it returns an [[ASGI]] response, which `Uvicorn` converts back into an HTTP response sent back to the client. 

Or simpler
- Browser sends HTTP request to Uvicorn,  Uvicorn converts it to [[ASGI]] and sends it to [[FastAPI]]. [[FastAPI]] completes its business logic and returns [[ASGI]] to Uvicorn, which will return a HTTP response to the client. 

```
Client
   │
   │ HTTP
   ▼
Uvicorn
   │
   │ ASGI
   ▼
FastAPI
   │
   │ application logic / routing / validation
   ▼
FastAPI
   │
   │ ASGI response
   ▼
Uvicorn
   │
   │ HTTP response
   ▼
Client
```





## [[Request Parsing]]


Parsing means taking raw unstructured input and turning it into structured data. [[Request parsing]] specifically means taking raw HTTP text, which includes methods, headers, the body and turning it into clean python values your code can use. 

FastAPI handles this entirely. A C HTTP server project is doing this manually so you can understand what the framework is doing.

## [[Dependency Injection]]


Instead of a function creating the things it needs itself, those things are provided *outside* of it. The function declares what it needs. The framework supplies it. 

``` python
def get_db():
	db = sessionLocal()
	try: 
		yield db
	finally:
		db.close()
	
@app.get("/urls/{code}")
def lookup(code: str, db = Depends(get_db)):
	return db.query(...)
```

The endpoint never creates the database session it
- declares the dependency,
- FastAPI injects it in 

This makes endpoints easier to test (swap in a fake Database) avoids repeating setup code and makes this unit layer of a test pyramid clean.




## [[Schema Generation]]

A schema is a formal description of the shape of data
- what fields exist
- what their types are
- which ones are required

In FastAPI you define schemas with Pydantic Models

``` python
class Metric(BaseModel):
	cpu : int
	host : str
```

Two things happen at once at declaration
1. Validation
	- Incoming requests that don't match this shape are automatically rejected before hitting our code
2. [[Schema Generation]]
	- FastAPI reads these models and automatically generates interactive [[API]] documentation at endpoint `/docs` 

With this we can declare  data shapes once and get access to validation and documentation for free.




# Scratch File
in a python file called `scratch_main.py` we do the following

```python
from fastapi import FastAPI
app = FastAPI()

@app.get("/ping")
def ping():
    return {"pong": True}

@app.get("/echo/{word}")
def echo(word: str):
    return {"you_said": word}
```


Then we run
`uvicorn scratch_main:app --reload
- to setup our server

and send a request using curl and the endpoints we made, specifically `/ping` and `/echo/{word}`

decorator `@app.get("/ping")` tells FastAPI which route will be connected to our path operation function `ping()` mapping the URL to the function. It then converts our python dict `{"pong": True}` and converts it into a JSON object


# Mental Model Note


What is `uvicorn` doing?

- FastAPI is a library of  python functions where as Uvicorn is the [[ASGI]] server that  listens on a port, accepts HTTP connections, and call our functions. 

what does `uvicorn app.main:app` mean?

- it means "in `app/main.py`" find the object named `app` and serve it".
- `--reload` is a command line argument that restarts the server automatically when we save a file
- `curl` is just a command-line orientated HTTP client to hit our endpoint without using a browser.

