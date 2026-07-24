We will be writing a few more tests but there is a slight issue. Do we want to test against the "production" database use "test" database or perhaps test against either and implement a rollback system so that our tests remain isolated?

So its probably better to setup a distinct database for the sake of isolation, and to have the rollback system setup so that tests aren't messing each other up within the test database.


so if we include the directory `/docker-entrypoint-initdb.d` and include a `.sql` file to create the test database we can create one after the initial database is setup.

```sql
CREATE DATABASE test_db;
```

Once that is done we need to save the database volume. We have this already setup. The next issue is we need to include the `test_db_init.sql` file into the `db` container. We can do this using a bind mount. In the volumes section of our `db` image in the docker compose file we include the following.

```yml
volumes:
  - ./host/path:container/path
```
- the path `./host/path` is relative to the docker compose file, while the `container/path` is absolute. So for our intentions this is what we do

```
volumes: # we create a volume so the data persists  
  - postgres_data:/var/lib/postgresql  
  - ./init/test_db_init.sql:/docker-entrypoint-initdb.d/test_db_init.sql
```


Now that we have a separate database we need to run the same migrations such that the schemas on the "test" database match the ones in the "prod"


Our original test database existed on the host machine. We want to now move it to run inside of the database service container. Since it no longer exists on the host machine this `DATABASE_URL` is no longer accurate
```
DATABASE_URL=postgresql://${SECRET_USERNAME}:${SECRET_PASSWORD}@localhost:5432/${DATABASE_NAME}
# Note that localhost no longer applies since we are working
# inside of the containers we convert it back to `db`
DATABASE_URL=postgresql://${SECRET_USERNAME}:${SECRET_PASSWORD}@db:5432/${DATABASE_NAME}
```

Then we consolidate our `.env` and `.env.test` files into a singular file.

``` env
SECRET_USERNAME=supersecretname  
SECRET_PASSWORD=supersecret  
DATABASE_NAME=db  
TEST_DATABASE_NAME=test_db  
DATABASE_URL=postgresql://${SECRET_USERNAME}:${SECRET_PASSWORD}@db:5432/${DATABASE_NAME}  
REDIS_URL=redis://redis:6379  
TEST_DATABASE_URL=postgresql://${SECRET_USERNAME}:${SECRET_PASSWORD}@db:5432/${TEST_DATABASE_NAME}
```


Now when we run the compose stack and run the migrations for the "prod" database we have the right tables setup. But our "test" database doesn't have the right tables setup.

All we need to do is do the same thing we did to run migrations for the "prod" database. That is create a new `app` container whose `DATABASE_URL` and `DATABASE_NAME` point to the test database instead of the prod database.


so this would work.
## Running migrations against the test database

To run Alembic migrations against the test database, we spin up a temporary app container with the test database credentials overridden via `-e`:

our `.env` looks like this right now
```
SECRET_USERNAME=  
SECRET_PASSWORD=  
DATABASE_NAME=  
TEST_DATABASE_NAME=  
DATABASE_URL=  
REDIS_URL=  
TEST_DATABASE_URL=
```

shell script
```bash
docker compose run \
  -e DATABASE_URL="$TEST_DATABASE_URL" \
  -e DATABASE_NAME="$TEST_DATABASE_NAME" \
  app alembic upgrade head
```

`-e` passes an environment variable into the container, overriding whatever is in the compose config. The `""` quotes around the values protect against spaces in the variable value.

The problem is that `$TEST_DATABASE_URL` and `$TEST_DATABASE_NAME` must actually be present in your shell for this to work. They live in `.env` but bash doesn't load `.env` automatically.

To load them:

```bash
set -a
source .env
set +a
```

`set -a` turns on auto-export mode -- every variable defined after this is automatically exported to subprocesses. `source .env` loads the variables from `.env` into your shell. `set +a` turns auto-export mode back off.

Without `set -a`, `source .env` loads the variables into your shell session but keeps them local -- subprocesses like `docker compose run` can't see them. With it, they're exported and visible to any subprocess you run after.

To avoid polluting our main shell session with the exported variables, we wrap everything in a subshell -- the variables only exist for the duration of the subshell and disappear when it exits:

```bash
(
	set -a
	source .env
	set +a
	docker compose run \
	  -e DATABASE_URL="$TEST_DATABASE_URL" \
	  -e DATABASE_NAME="$TEST_DATABASE_NAME" \
	  app alembic upgrade head
)
```


Some things we learnt
- Learned how the Postgres initialization scripts work.
- Learned how Docker Compose injects environment variables.
- Learned the difference between shell variables and exported environment variables.
- Learned that `docker compose run` creates a temporary container whose environment can be overridden.


# Test Isolation via Transaction Rollback


The goal is to let each test test against the database by calling `session.connect()` without allowing tests to leave any data behind

## Two-layer structure

```
Outer transaction (owned by the test fixture)
│
├── SAVEPOINT  ← session.commit() becomes this
├── SAVEPOINT
├── SAVEPOINT
│
└── rollback   ← undoes everything, database is clean again
```
## How it works

Step 1: Open connection

```python
connection = engine.connect()
```

Step 2: Start the outer transaction

```python
trans = connection.begin()
```

Step3: Create the session

```python
session = Session(bind=connection, join_transaction_mode="create_savepoint")
```

The session uses the same connection as the outer transaction. `create_savepoint` will tell SQLAlchemy to intercept each call to `session.commit()` and convert it to `SAVEPOINTS` rather than actual commits to the database

Step 4: Tests runs

The test code calls `session.commit()` as normal. From the tests perspective everything is working as normal. But from the databases perspective nothing is permanently committed. Everything happens inside of save points in the outer transaction.

Step 5: Teardown

``` python
trans.rollback()
connection.close()
```

So instead of doing `commit` instead we create savepoints

You can call `session.rollback()` to rollback specific savepoints and the end doing `trans.rollback()` rolls back the outer transaction.



## Setting up `conftest.py`

`conftest.py` is the configuration file that pytest will use to hold our test fixtures shared between tests. Pytest automatically finds it so we don't need to import from it


### What is a fixture?

A fixture is a function that sets up things before a test and tears it down after. Instead of repeating setup code every test we can define the fixture in `conftest.py` and pytest will inject it into any test that askes for it by name


For ours we'll have the following:

- test database engine pointed at `test_db`
- rollback fixture setup
- dependency override so FastAPI will use the test session instead of `get_db`
- the `TestClient` so every test can make HTTP requests against the app



































































