# Command Reference

> AI-generated reference sheet for commands I've learned while working with Linux and my development environment.

## Docker Compose

### Build and start all services

```bash
docker compose up --build
```

### Start all services in the background

```bash
docker compose up -d
```

### Start a specific service

```bash
docker compose up -d <<service>>
```

### Stop all services and remove containers, networks, and volumes

```bash
docker compose down -v
```

### Run a command in a new container

```bash
docker compose run <<service>> <<command>>
```

### Run a command in an existing container

```bash
docker compose exec <<service>> <<command>>
```

### View logs for a service

```bash
docker compose logs <<service>>
```

---

## Alembic

### Initialize Alembic

```bash
alembic init alembic
```

### Generate a migration

```bash
alembic revision --autogenerate -m "<<message>>"
```

### Apply all pending migrations

```bash
alembic upgrade head
```

---

## PostgreSQL (psql)

### Connect to a database inside a container

```bash
docker compose exec <<service>> psql -U <<username>> -d <<database_name>>
```

### List all tables

```sql
\dt
```

### Describe a table

```sql
\d <<table_name>>
```

### Exit psql

```sql
\q
```

---

## File Permissions

### Change file ownership

```bash
sudo chown <<username>> <<filename>>
```

### Change file permissions

```bash
sudo chmod <<permissions>> <<filename>>
```

### Open a file as root

```bash
sudo vim <<filename>>
```

---

## Environment Variables

### Set an environment variable for the current shell

```bash
export <<variable>>=<<value>>
```

### Load environment variables from a `.env` file

```bash
export $(cat .env | xargs)
```

### Verify an environment variable

```bash
echo $<<variable>>
```
