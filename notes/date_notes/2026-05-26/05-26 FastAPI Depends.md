# Dependency Injection (FastAPI)

A way for our code to declare things it will require to work, its "dependencies", and then have a system (FastAPI in our case) take care of providing them.

Instead of a function creating the things it needs itself, those things are provided to it from outside. The function declares what it needs. The framework supplies it.

Useful when we need to:

- Share logic that would otherwise be repeated across routes
- Share database connections
- Enforce security, authentication, or role requirements

---

## The Problem Without DI

Every route is responsible for creating and cleaning up its own database session:

```python
@app.get("/targets")
def list_targets():
    db = SessionLocal()
    try:
        return db.query(Target).all()
    finally:
        db.close()

@app.get("/targets/{id}")
def get_target(id: int):
    db = SessionLocal()
    try:
        return db.query(Target).filter(Target.id == id).first()
    finally:
        db.close()
```

Problems:

- Repeated setup and cleanup code in every route
- Easy to forget `db.close()` and leak connections
- If session creation ever changes, every route needs updating

---

## With DI

Define the session lifecycle once:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Because `get_db()` has a `yield` it is a generator function. FastAPI treats everything before the yield as setup and everything after it as teardown. FastAPI will guarantee that everything after the `yield` will run even if the route raises an exception. 

Use it in routes:

```python
@app.get("/targets")
def list_targets(db = Depends(get_db)):
    return db.query(Target).all()

@app.get("/targets/{id}")
def get_target(id: int, db = Depends(get_db)):
    return db.query(Target).filter(Target.id == id).first()
```

The endpoint never creates the session itself , it declares the dependency, and FastAPI injects it.

---

## What `Depends(get_db)` Actually Does

```python
db = Depends(get_db)
```

This tells FastAPI: _"this route needs a database session — get it by calling `get_db()`."_

FastAPI will:

1. Call `get_db()`
2. Create the database session
3. Pass it into the route as `db`
4. Run the route
5. Resume `get_db()` after the `yield` and close the session

---

## Important Note

DI does not magically create database connections. We still define how a session is created:

```python
def get_db():
    db = SessionLocal()
    ...
```

The advantage is that this logic is written once and reused everywhere via `Depends(get_db)` instead of being repeated in every route.

---

## Testing Benefit

Because the route never directly calls `SessionLocal()`, tests can swap the dependency out entirely without touching any route code:

```python
def get_test_db():
    yield fake_dict  # or a test DB session pointed at a test database

app.dependency_overrides[get_db] = get_test_db
```

This keeps the unit layer of the test pyramid clean — routes can be tested in isolation from a real database.



