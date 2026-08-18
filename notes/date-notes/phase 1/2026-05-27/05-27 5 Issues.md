## CRLF Line Endings in `.env` Files

### The issue

Windows line endings (`\r\n`) vs Unix line endings (`\n`).

When a `.env` file is created or edited on Windows, each line ends with `\r\n`. On Linux/Mac, lines end with `\n`. When `python-dotenv` reads a file with CRLF endings, the `\r` gets included in the variable value:

```
supersecretname\r
```

That `\r` gets passed into the database connection string:

```
user='supersecretname\r' password='supersecret\r'
```

Postgres sees a username that doesn't exist and returns a password authentication error -- even though the credentials are correct.

### How to fix

Running the following command tends to work:

```bash
dos2unix <<filename>>
```

---

## Test Environment Issue: Local pytest vs Docker Compose Networking

### The problem

Our PostgreSQL server runs inside a Docker container. This same instance contains both the development database and the test database.

We prefer running tests locally because PyCharm's debugger makes it easier to step through failures.

`test_health()` works fine locally -- it only checks that the app responds and never touches the database.

`test_ready()` fails. The execution flow is:

```
test_ready()
    |
TestClient.get("/ready")
    |
main.py::ready()
    |
Depends(get_db)
    |
Session
    |
DATABASE_URL = postgresql://...@db:5432/db
```

`ready()` gets a database session through FastAPI's dependency injection. `get_db()` yields a SQLAlchemy session built from an engine configured with `DATABASE_URL`.

Inside our Docker Compose network, `db` resolves to the PostgreSQL container via Docker's internal DNS. Running locally, the Python process has no knowledge of that network -- there is no hostname named `db`.

The failure happens before any test logic runs:

```
test_ready()
    |
get_db()
    |
DATABASE_URL
    |
hostname "db" cannot be resolved locally
```

### Possible solutions considered

**1. Create a local test database** Not sufficient by itself. The failure occurs while connecting to the primary database. The test database is not involved at this stage.

**2. Modify `get_db()`** Possible but undesirable. `get_db()` is responsible for providing a session, not for selecting which environment to run in. The problem is configuration, not dependency injection.

**3. Maintain separate local environment variables** We could provide a `.env.local` file where Docker-specific hostnames like `db` are replaced with `localhost`. This solves the immediate problem, but introduces separate configuration for local and containerized execution.

One approach is to source `.env.local` into the shell before running pytest:

```bash
set -a
source .env.local
set +a
pytest
```

This works, but it exports sensitive values like database credentials directly into our shell environment. That goes against one of the reasons for using Docker in the first place -- keeping secrets and environment-specific configuration contained and not leaking into the host machine. Any process running in that shell session could read those values.

A cleaner approach is to wrap the sourcing in a subshell so the variables only exist for the duration of the command and disappear immediately after:

```bash
(set -a; source .env.local; set +a; pytest)
```

This limits exposure but the credentials are still briefly present in the host environment. More importantly, both approaches require running pytest from the command line. There is no straightforward way to have PyCharm first run the sourcing script and then launch its debugger, so while this fixes the connection issue, stepping through tests interactively in PyCharm is still not possible.

**4. Configure PyCharm's debugger with its own environment file** PyCharm allows a separate environment file for the debugger. This avoids modifying application code, but PyCharm does not expand placeholder variables the same way Docker Compose does, requiring changes to our existing variable structure.

**5. Select the database URL conditionally** We could introduce an environment variable that indicates tests are running. When present, configure the SQLAlchemy engine with `TEST_DATABASE_URL` instead of `DATABASE_URL`. This keeps the rest of the application unchanged but adds conditional logic to our database configuration.

**6. Run tests inside Docker** Running `pytest` inside the app container eliminates the hostname problem since `db` resolves correctly within our Compose network. The drawback is losing PyCharm's interactive debugger.

### Solution

We solved the issue by loading both environment files in `conftest.py`:

```python
load_dotenv(".env")
load_dotenv(".env.local", override=True)
```

`.env` provides the default configuration used by our Docker Compose environment. `.env.local` overrides only the values that differ when we run tests locally -- for example, using `localhost` instead of Docker's `db` hostname.

### Mental blocker

We initially avoided this approach because we thought loading `.env.local` would affect the running Docker containers.

It does not.

`conftest.py` is only executed by the local `pytest` process. Our application containers never run the test suite, so they never import `conftest.py` or load `.env.local`. The execution environments are completely separate:

```
Docker Compose
    |
Container
    |
Uses .env
```

```
Local pytest
    |
conftest.py
    |
Loads .env
Loads .env.local (override=True)
```

If we ran tests inside the application container instead, the opposite problem would occur -- the container would load `.env.local` and try to connect to `localhost`, which inside the container refers to the container itself, not the PostgreSQL service. This solution works specifically because our tests run on the host machine, not inside Docker.

Since `conftest.py` handles environment loading automatically, we no longer need to touch PyCharm's run configuration or manually source files before running tests. This also means our `.env` and `.env.local` files can use placeholder values safely -- the real credentials never need to appear in any configuration file that gets committed, and no manual steps are required before running the test suite.

The key realization was that `conftest.py` is never executed by our containers at all. It is purely a pytest artifact -- the containers run the application, not the test suite. There is no pytest process inside the containers, no test runner, nothing that would ever import or execute `conftest.py`. Once that clicked, the concern about `.env.local` affecting the containers disappeared entirely. Our two execution environments are completely separate and never interact.



## Trailing slash consistency in route definitions

While writing `scripts/create-target-example.sh`, we noticed our `curl` POST to `http://localhost:8000/targets` was failing. The cause was a inconsistency in `app/routers/targets.py`: the POST route was defined as `"/"`, which combined with the `/targets` router prefix in `main.py` made the full path `/targets/`. Our other routes (`GET ""`, `GET "/{id}"`, `PATCH "/{id}"`) used no trailing slash.

The REST convention is no trailing slash. A trailing slash implies a directory, not a resource. We changed the POST route from `"/"` to `""` to match the rest of the router, making all endpoints consistent under `/targets`.