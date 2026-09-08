# GitHub Actions CI Pipeline

## Goal

The goal of our first CI pipeline is simple:

```text
push to main
    ↓
GitHub creates a temporary runner
    ↓
repository is checked out
    ↓
Python is configured
    ↓
project dependencies are installed
    ↓
CI environment variables are provided
    ↓
Docker Compose stack starts
    ↓
PostgreSQL and Redis become ready
    ↓
database migrations run
    ↓
pytest receives its local overrides
    ↓
tests pass or fail
```

At this stage, the workflow is only responsible for **continuous integration**. It is not deploying anything to Azure.

The purpose is to prove that the project can be checked out onto a clean machine, have its dependencies recreated, and successfully run the complete test suite.

---

## Triggering the Workflow

We want the CI workflow to run whenever a commit is pushed to the `main` branch.

Since `main` is currently the only branch we are working with:

```yaml
on:
  push:
    branches:
      - main
```

Conceptually:

```text
git push origin main
        ↓
GitHub receives push event
        ↓
Synthetic CI Pipeline starts
```

---

## Creating the Job

A workflow contains one or more jobs.

For this workflow, we only need one:

```yaml
jobs:
  test:
```

The name `test` is arbitrary. We could call the job `build`, `ci`, or something else.

The name should simply describe what the job is responsible for.

---

## Choosing the Runner

Each job needs a runner.

For CI we use a GitHub-hosted Linux runner:

```yaml
runs-on: ubuntu-latest
```

GitHub creates a temporary Ubuntu virtual machine for the job.

Conceptually:

```text
GitHub
   ↓
temporary Ubuntu VM
   ↓
our job executes
   ↓
VM is discarded afterward
```

We do not manually configure the GitHub runner itself.

The runner already includes tools such as Docker, but project-specific dependencies still need to be configured explicitly.

---

# Checking Out the Repository

The fresh runner does not initially contain our project.

The first step therefore checks out the repository:

```yaml
steps:
  - name: Grab the repository
    uses: actions/checkout@v4
```

`actions/checkout` places the repository inside the runner's workspace.

Subsequent commands execute from the repository workspace by default, which means commands such as:

```bash
pip install -r requirements.txt
docker compose up
./scripts/migrate.sh
pytest
```

can continue using paths relative to the project root just as they do locally.

### Why `actions/checkout@v4`?

The `@v4` pins us to a major version of the Action.

This is similar to deliberately choosing a Python or dependency version rather than depending on an unspecified implementation.

---

# Setting Up Python

Our tests run directly on the runner, so the runner needs the Python version expected by the project.

GitHub provides the `setup-python` Action:

```yaml
- name: Install Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.12'
```

Even though GitHub runners already contain Python installations, explicitly selecting the version prevents our CI environment from depending on whatever version happens to be the runner default.

---

# Installing Dependencies

The repository now exists and Python is configured, but the project's Python dependencies still need to be installed.

We use:

```yaml
- name: Install all dependencies
  run: pip install -r requirements.txt
```

`requirements.txt` itself is not executed.

Instead, `pip` reads the file and installs the dependencies listed inside it.

This gives the runner the packages required by the application and test suite, including pytest.

---

# Configuration and Secrets

## The Local Configuration Model

Locally, the project uses two configuration files:

```text
.env
.env.local
```

Both are gitignored, so neither exists after GitHub checks out the repository.

Originally, it seemed like CI could simply provide the **final environment-variable values** that exist after `.env.local` overrides `.env`.

That turned out to be incorrect.

The important realization is that `.env` and `.env.local` represent **different execution contexts**.

---

## Base Configuration

The normal `.env` values are intended for processes running inside the Docker Compose environment.

For example:

```text
DATABASE_URL → PostgreSQL host = db
REDIS_URL    → Redis host = redis
```

Inside the Compose network:

```text
app container
    |
    +---- db:5432
    |
    +---- redis:6379
```

The service names `db` and `redis` are resolved by Docker Compose networking.

These values therefore need to remain available while we:

- start the Compose stack
    
- run application containers
    
- run migrations from the container environment
    

---

## Local Test Overrides

Pytest is different.

Pytest runs directly on the host machine rather than from inside the Compose network.

Locally that means:

```text
development machine
│
├── pytest
│
└── Docker Compose
     ├── PostgreSQL
     └── Redis
```

Therefore pytest cannot use:

```text
db
redis
```

as hostnames.

Instead it connects through the ports Docker publishes onto the host:

```text
localhost:5432
localhost:6379
```

This is what `.env.local` handles locally.

Conceptually:

```text
.env
DATABASE_URL → db:5432
REDIS_URL    → redis:6379

        ↓ override for pytest

.env.local
DATABASE_URL → localhost:5432
REDIS_URL    → localhost:6379
```

The GitHub runner has exactly the same topology:

```text
GitHub runner
│
├── pytest
│
└── Docker Compose
     ├── PostgreSQL
     └── Redis
```

Therefore CI needs to reproduce the same configuration boundary.

---

# Job-Level Environment

The normal Compose configuration is placed at the **job level**:

```yaml
env:
  DATABASE_URL: ${{ secrets.DATABASE_URL }}
  POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}
  POSTGRES_USER: ${{ secrets.POSTGRES_USER }}
  REDIS_URL: ${{ secrets.REDIS_URL }}

  POSTGRES_DB: ${{ vars.POSTGRES_DB }}
  TEST_DATABASE_NAME: ${{ vars.TEST_DATABASE_NAME }}
```

Job-level environment variables are available to every step unless a step overrides them.

Conceptually:

```text
job environment
      |
      +-- Docker Compose
      +-- migrations
      +-- other commands
      |
      +-- pytest
            ↓
        may override values
```

---

# GitHub Environment

The secrets and variables are stored inside a GitHub Environment named:

```text
CI/CD environment
```

Because they are environment-level values, the job must explicitly reference that environment:

```yaml
environment:
  name: "CI/CD environment"
```

Without this, expressions such as:

```yaml
${{ secrets.POSTGRES_PASSWORD }}
```

were resolving to empty values because the job did not have access to the environment containing the secret.

This produced our first CI failure:

```text
PostgreSQL starts
    ↓
POSTGRES_PASSWORD is empty
    ↓
PostgreSQL refuses to initialize
```

Adding the environment reference made those values available to the job.

---

# Starting Docker Compose

The runner already contains Docker.

We first pull the external images referenced by the Compose configuration:

```yaml
- name: Pull images for the runner
  run: docker compose pull
```

Then start the stack:

```yaml
- name: Start the Docker Compose Stack
  run: docker compose up --build -d
```

`--build` ensures buildable services are rebuilt using the source code checked out by the workflow.

`-d` starts the services in detached mode so the workflow can continue to later steps.

The resulting runner looks roughly like:

```text
GitHub runner
│
├── project source
├── Python / pytest
│
└── Docker Compose
     ├── app
     ├── PostgreSQL
     ├── Redis
     ├── Prometheus
     ├── Grafana
     └── Alertmanager
```

---

# Inspecting the Stack

During initial CI setup we added diagnostic steps:

```yaml
- name: Show Docker Compose status
  run: docker compose ps -a

- name: Show Postgres logs
  run: docker compose logs db
```

These were useful because a failed CI job could distinguish between:

```text
container failed to start
```

and:

```text
container is running but service is not ready
```

The Postgres logs were particularly useful when diagnosing the missing `POSTGRES_PASSWORD`.

---

# Waiting for Dependencies

`docker compose up -d` returning successfully only proves that Docker started the containers.

It does **not** necessarily mean the services inside those containers are ready.

For example:

```text
Postgres container running
        ≠
Postgres accepting connections
```

We therefore explicitly poll PostgreSQL and Redis:

```yaml
- name: Wait for Postgres and Redis
  run: |
    until docker compose exec -T db pg_isready -U postgres; do sleep 1; done
    until docker compose exec -T redis redis-cli ping; do sleep 1; done
```

Conceptually:

```text
start containers
      ↓
PostgreSQL accepting connections?
      ↓ yes
Redis responding to PING?
      ↓ yes
continue
```

This avoids a race where pytest starts while a dependency is still initializing.

---

# Database Migrations

A GitHub-hosted runner starts from scratch every time.

Unlike our development machine, it has no existing PostgreSQL volume containing previously migrated tables.

Therefore the workflow must explicitly recreate the database schema.

We run the migration script after PostgreSQL is ready:

```yaml
- name: Run alembic migrations for test database
  run: ./scripts/migrate.sh
```

This exposed another useful difference between local development and CI:

```text
local machine
    ↓
persistent PostgreSQL volume
    ↓
schema already exists

CI runner
    ↓
brand-new PostgreSQL container
    ↓
empty database
    ↓
migrations required
```

A clean CI environment forces us to recreate assumptions that our local machine may already satisfy.

---

# Problems Found While Building CI

Building the workflow exposed several assumptions that were hidden by the existing development machine.

### 1. GitHub Environment was not referenced

The secrets existed, but they were stored under:

```text
CI/CD environment
```

The job did not initially reference that environment.

Result:

```text
POSTGRES_PASSWORD = empty
        ↓
Postgres exits during initialization
```

Fix:

```yaml
environment:
  name: "CI/CD environment"
```

---

### 2. Migration networking used the wrong context

We initially attempted to use `localhost` while executing Alembic from a container.

Inside a Compose container:

```text
localhost → current container
db        → PostgreSQL container
```

The migration environment therefore needs the Compose version of the database connection.

---

### 3. Fresh CI databases had no schema

The local PostgreSQL volume already contained migrated tables.

CI starts from an empty database every time.

Result:

```text
relation "endpoint_target" does not exist
```

The migrations therefore need to run before pytest.

---

### 4. Pytest initially inherited Compose hostnames

Some tests attempted to connect to:

```text
db:5432
```

from the GitHub runner.

`db` only exists as a hostname inside the Compose network.

Pytest therefore needs its local overrides:

```text
localhost:5432
localhost:6379
```

---
# Final CI Workflow

```yaml
name: Synthetic CI Pipeline

on:
  push:
    branches:
      - main

jobs:
  test:
    runs-on: ubuntu-latest

    environment:
      name: "CI/CD environment"

    env:
      DATABASE_URL: ${{ secrets.DATABASE_URL }}
      POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}
      POSTGRES_USER: ${{ secrets.POSTGRES_USER }}
      PROMETHEUS_URL: ${{ secrets.PROMETHEUS_URL }}
      REDIS_URL: ${{ secrets.REDIS_URL }}
      GF_SECURITY_ADMIN_USER: ${{ secrets.GF_SECURITY_ADMIN_USER }}
      GF_SECURITY_ADMIN_PASSWORD: ${{ secrets.GF_SECURITY_ADMIN_PASSWORD }}
      TEST_DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}

      TEST_DATABASE_NAME: ${{ vars.TEST_DATABASE_NAME }}
      POSTGRES_DB: ${{ vars.POSTGRES_DB }}
      SCHEDULER_ENABLED: ${{ vars.SCHEDULER_ENABLED }}

    steps:
      - name: Grab the repository
        uses: actions/checkout@v4

      - name: Install Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install all dependencies
        run: pip install -r requirements.txt

      - name: Pull images for the runner
        run: docker compose pull

      - name: Start the Docker Compose Stack
        run: docker compose up --build -d

      - name: Show Docker Compose status
        run: docker compose ps -a

      - name: Show Postgres logs
        run: docker compose logs db

      - name: Wait for Postgres and Redis
        run: |
          until docker compose exec -T db pg_isready -U postgres; do sleep 1; done
          until docker compose exec -T redis redis-cli ping; do sleep 1; done

      - name: Run alembic migrations for test database
        run: ./scripts/migrate.sh

      - name: Run pytest
        env:
          TEST_DATABASE_URL: ${{ secrets.LOCAL_TEST_DATABASE_URL }}
          DATABASE_URL: ${{ secrets.LOCAL_DATABASE_URL }}
          REDIS_URL: ${{ secrets.LOCAL_REDIS_URL }}
        run: pytest
```
