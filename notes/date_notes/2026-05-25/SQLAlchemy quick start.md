
Parts to cover

- Declare Models
- Create an Engine
- Emit Create Table DDL
- create objects and persist

Look at the bottom of create objects and persist, showing the actual SQL firing


## Declaring Models


### The Base Class

``` python
class Base(DeclarativeBase):
	pass
```

The starting point. Every model class we write will inherit from `Base`. SQLAlchemy uses this to determine which classes represent database tables. 


### A Model Class

example:
```python
class User(Base):
	__tablename__ = "user_account"
	
	id: Mapped[int] = mapped_column(primary_key=True)
	name: Mapped[str] = mapped_column(String(30))
	fullname: Mapped[Optional[str]]
```

There are 3 things going on here. 
1. `__tablename__` this part tells SQLAlchemy which actual table in Postgres our class maps to. If we wanted to name our table something like `"day_grocery_list"` we would do it here
2. `Mapped[int]` is a type annotation. SQLAlchemy reads this to know the given column's SQL type. 
	- `int` becomes `INTEGER`
	- `str` becomes `VARCHAR`
3. `mapped_column(...)` we use this part to add extra configuration. 
	- we see its used to set `id` to be the primary key
	- isn't necessary as we see `fullname` omits it
4. `Optional[str]` means that the column is nullable.

>[!Danger] If you do not set a column to `nullable` SQLAlchemy will assume a column is `NOT NULL`



## The Foreign key and the relationship


```python
class Address(Base):
	__tablename__ = "address"
	
	id: Mapped[int] = mapped_column(primary_key=True)
	email_address: Mapped[str]
	user_id: Mapped[id] = mapped_column(ForeignKey("user_account.id"))
	user: Mapped["User"] = relationship(back_populates="addresses")
```

the line `ForeignKey("user_account.id")` is the database level constraint. 
- it tells postgres that `user_id` must refer to a valid `id` in the `user_account` table

`relationship(...)`  instead is a python level convenience. It actually doesn't create anything within the database. It lets us do `address.user` to get the `User` object associated with that address. Instead of writing a join query.

What `back_populates` does is wire the two sides together. so that `User.address` and `Address.user` form two sides of the same relationship. 




## Nullability

>Nullability derives from whether or not the `Optional[]` type modifier is used.


This means that a given column's nullability is controlled by the type annotation

```python
name: Mapped[str]                # Not NUll
fullname: Mapped[Optional[str]]  # Nullable
```



## The Engine

The engine isn't a connection, rather its a [[Factory|factory]] that knows how to create connections. It also manages a list of requests so you don't have to constantly open a new TCP connection every time.

```
engine
├── knows the database URL
├── manages the connection pool
└── hands connections to Sessions when asked
```

since we'll be using the engine a lot, it needs to know what the database URL which we store as an environmental variable.
Recall we can access environment variables in python using by importing `os` and using the line `os.environ[<<env_name>>] `

``` python
engine = create_engine(os.environ["DATABASE_URL"])
```

the parameter `echo=True` prints every SQL statement `SQLAlchemy` generates to `stdout` useful for seeing how SQLAlchemy converts python statements into SQL


## `Base.metadata.create_all(engine)`

This line has 3 parts

1. `Base.metadata`
	- holds everything SQLAlchemy knows about our tables (names, columns, types, foreign keys) stored as a description, not a table yet
2. `create_all()` 
	- reads the description, generates `CREATE TABLE` statements sends them to a database
3. `engine`
	- provides the connection to send them through.




## Why we won't be using `create_all()` much

in the docs `create_all()` will actually issue a `CREATE TABLE IF NOT EXISTS` that is it will generate the table schema if it can't find it. But if the table already exists and we which to add a new column `create_all()` will do nothing. 
- one solution would be to drop the table and then use the new table structure to generate the `CREATE TABLE` statements but what would be the point in that?
- Another solution would be to write the `ALTER TABLE` by hand

This issue is why we are using Alembic on day one. It will handle the `ALTER TABLE` case so the monitoring history survives schema changes.






# Session : Our Day-to-Day interface to the database

The engine makes the connection, whereas the session is how we actually work with the data

```
Engine  = knows how to reach the database
Session = workspace for reading and writing data 
```


## Creating Objects and Persisting them

example:
``` python
with Session(engine) as session:
	spongebob = User(name = "spongebob", 
	                 fullname = "Spongebob Squarepants")
	                 session.add_all([spongebob, sandy, patrick])
					 session.commit()
```

Three steps to this that must be in order
1. Create the object. `User(name="spongebob")` just python
2. `session.add()` this tells SQLAlchemy "track this object, I intend to save it". still no SQL, no database write
3. `session.commit()`. Now SQLAlchemy will generate and send in the insert. 

```
create object  →  session.add()  →  session.commit()  →  INSERT happens
```

The reason for these steps is to stay connected to a transaction model. Nothing is permanently saved until `commit()` is complete. If there are any crashes between `add()` and `commit()` the database will automatically rollback 

>[!Question] Why do we use a `with` block?
>`with Session(engine) as session:` is used since sessions once opened need to be closed, and python provides a natural closing with the `with` block


## Simple SELECT

```python
stmt = select(User).where(User.name.in(["spongebob", "sandy"]))
for user in session.scalars(stmt):
	print(user)
```

`select(USER).where(...)` builds a query as a Python object, but there isn't any SQL sent yet. 

`session.scalars(stmt)` is what executes the query and returns ORM objects, not raw tuples. which means we can do `user.name` instead of `row[1]` 😮 🤯 💥

# Summary

``` text
Models define the schema.
Base.metadata stores that definition.
Engine knows how to reach the database.
create_all() turns the definition into real tables.
```


