
# ADR-001: FastAPI vs Django

## Context

- I wanted to build a project that combines Backend and DevOps tooling. I selected to create a service where URLs are registered, afterwards we send periodic HTTP request to them, record the result and expose the data for alerting and visualization. 

## Decision

- I wanted a simple framework that's lightweight and doesn't have anything unnecessary included, but also comes with just enough "in the box" to not have to call too many third party libraries
## Alternatives Considered

- Django
	- Since I wanted a small and pure JSON API Django just comes with too much extra stuff I didn't really need
- Flask
	- Flask has the opposite problem that Django has. Flask doesn't come with built in validation or documentation

So FastAPI comes with what I need, but not too many useless functionality (for my use case anyways)





## Consequences

Consequences of selecting FastAPI

- Pros:
	- Lightweight
	- built-in validation and OpenAPI documentation
- Cons:
	- Never used FastAPI before
	- Not as popular as Django, so there may be fewer tools that I can use with it


