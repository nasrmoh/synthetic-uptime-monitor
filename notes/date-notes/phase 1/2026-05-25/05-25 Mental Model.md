 📐 MENTAL MODEL — SQLAlchemy & Alembic SQLAlchemy maps Python objects and expressions to SQL so you work with rows as objects instead of hand-writing query strings (and hand-rolling injection risks). Alembic exists because schema changes need version history, review, and repeatability — without migrations your local, test, and future server databases drift silently, and `metadata.create_all()` can't safely evolve a populated table without dropping it. SQLAlchemy hides connection pooling, dialect differences, and object-row mapping, but it does **not** remove the need to understand the SQL being run (watch for N+1 queries). Alternatives: raw psycopg, Django ORM, SQLModel, asyncpg.



## SQLAlchemy and Alembic

### SQLAlchemy
SQLAlchemy is a python library that lets you work with database rows as python objects instead of writing SQL strings by hand

Without it:

``` python
cursor.execute("""

	INSERT INTO monitor_targets (url, expected status)
	VALUES (%s, %s)
	""", (url, expected_status))
```
With it:

```python
target = EndpointTarget(url="https://google.com", expected_status=200)
session.add(target)
session.commit()
```


SQLAlchemy creates the `INSERT` behind the scenes. Same holds for reads. 

`session.query(EndpointTarget).filter(EndpointTarget.enabled == True)`

gets converted by SQLAlchemy into `SELECT * FROM monitor_targets WHERE enabled = true`. 


We have the following mappings which are bidirectional
- Python class definitions $\iff$ Table Schemas
- Python Expressions $\iff$ SQL clauses
- Python Objects with Attributes $\iff$ Database Rows



### Alembic

This is a library separate from [[SQLAlchemy]] by the same author. It tracks how the schema changes over time. Where SQLAlchemy answers "What does the database look like right now?" Alembic answers "How did we get here? and how do we change it safely"




## Why `create_all()` is not enough



Consider the lifetime of a proect.

### Day 1

You write:

```python
class EndpointTarget(Base):
	__tablename__ = "endpoint_targets"
	
	id: Mapped[int] = mapped_column(primary_key=True)
	url: Mapped[str]
```

Now your database is empty

You then run:

```python
Base.metadata.create_all(engine)
```

SQLAlchemy sees:

>The `endpoint_targets` table doesn't exist

so it will then generate:

```SQL
CREATE TABLE endpoint_targets (
	id INTEGER PRIMARY KEY,
	url TEXT NOT NULL
);
```

Which works fine, but what happens on day 30?


### Day 30

Now that you've been collecting monitoring data for a month, your table looks like the following


| id  | url                |
| --- | ------------------ |
| 1   | https://google.com |
| 2   | https://openai.com |

You want to change your model to include a timeout feature

```python
class EndpointTarget(Base):
	__tablename__ = "endpoint_targets"
	
	id: Mapped[int] = mapped_column(primary_key=True)
	url: Mapped[str]
	timeout_seconds: Mapped[int]
```

But you would expect `SQLAlchemy` to execute this:
```sql
ALTER TABLE endpoint_targets
ADD COLUMN timeout_seconds INTEGER;
```


### What does `create_all()` exactly do?

All it will do is check if a table exists, if it does then it will do nothing.

#### Why not just recreate the table?

Doing this would be an issue if you have data inside of your tables


### Alembic's Role

Alembic keeps a history of the schema changes.

Example:

Migration 001
```sql
CREATE TABLE endpoint_targets (...);
```

Migration 002
```sql
ALTER TABLE endpoint_targets
ADD COLUMN timeout_seconds INTEGER;
```

 Migration 003

``` sql
CREATE INDEX idx_target_urlON endpoint_targets(url);
```


### So what's the value?

suppose there are multiple schema instances across different laptops. Without alembic these schemas will be inconsistent. By using Alembic, you can run the command

```bash
alembic upgrade head
```












































