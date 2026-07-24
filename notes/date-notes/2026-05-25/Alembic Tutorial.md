## What Alembic Really Is


Alembic keeps a history of every schema change, not just a snapshot of the current state. Each change is its own migration file. The chain of files is the full history of how the database got to its current shape.

## `alembic revision`

```bash
alembic revision -m "create account table"
```
- this just creates a file, with the `-m` flag creates a human readable tag for the filename

The generated file:

``` python
revision = '1975ea83b712'
down_revision = None

def upgrade():
    pass

def downgrade():
    pass
```

You are given a shell, which you have to fill in.



## `upgrade()` and `downgrade()`



```python
def upgrade():
    op.create_table('account', ...)

def downgrade():
    op.drop_table('account')
```
`upgrade()` is how you move forward, whereas `downgrade()` is how you move back. the `op.` functions are Alembic's way of doing schema operations. Each one generates some SQL

```
op.create_table() -> CREATE TABLE
op.add_column()   -> ALTER TABLE ADD COLUMN
op.drop_table()   -> DROP TABLE
op.create_index() -> CREATE INDEX
```

## `down_revision` Is creates the chain

```python
# Migration A
revision = 'A'
down_revision = None      # first migration, nothing before it

# Migration B
revision = 'B'
down_revision = 'A'       # points back to A

# Migration C
revision = 'C'
down_revision = 'B'       # points back to B
```

Alembic reads the files in `versions/` and follows the down revisions to build an ordered list. This is how it knows how to run the changes in order.


## `alembic upgrade head`

This is the command that changes the database. Three things happen

1. Alembic checks the current `alembic_version`, if the table doesn't exist yet it will be created
2. it calculates which migrations haven't been applied
3. it runs each missing `upgrade()`, in the correct order and updates the `alembic_version`

> Head just means the current most recent `alembic_version` it is possible to target a specific version 




### `alembic_version`
```
alembic_version
version_num
--------------------
1975ea83b712
```
a single-column table that Alembic manages automatically. It stores which migration we are currently on.


# Summary

```
1. alembic revision   → creates a file, not a database change
2. upgrade()          → how to move the schema forward
3. downgrade()        → how to undo it
4. down_revision      → links migrations into an ordered chain
5. alembic upgrade head → runs missing migrations, updates alembic_version
```




## Alembic Setup

run `alembic init alembic` which will generate
```
alembic/
    versions/      ← migration files live here
    env.py         ← configure this before running migrations
    script.py.mako ← template Alembic uses to generate new migration files
alembic.ini        ← main Alembic config file
```

We need to make two changes. Completed within the `/alembic/env.py` file

1. Tell alembic about our models
```
from app import Base
target_metadata = Base.metadata
# we replace the line target_metadata = None
```

2. Tell Alembic where the database is

```
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
```
- alembic will read from alembi.ini but we want to use the environment variable `DATABASE_URL` which we outline in the docker compose yaml file.
	- after the line `config = context.config`
> Probably easier to control via an environment variable? Hmmm I do not know


Then we run the following commands

```
# Generate migration
alembic revision --autogenerate -m "message tag"
# apply it to database
alembic upgrade head
```

there's an issue with the database url not being set. To fix this we would do the following.

```bash
export DATABASE_URL=postgresql://<<username>>:<<password>>@localhost:5432/<<database_name>>
```
- but this only holds for the current terminal session, and since it contains secrets we don't want to do this. Anyways we don't want to do this anyways as our project is supposed to be containerized

- Since we are working with containers all we need to do is set the database URL environment variable within our docker compose yml. 

```
services:
  app:
    environment:
    - DATABASE_URL=<<value>>
```

- Then run the command within the container, as the container has the necessary configuration details we want. 

``` 
# if the container isn't running
docker compose run <<service>> <<command>>
# if the container is running
docker compose exec <<service>> <<command>>
```

or more specifically
```
docker compose run app alembic revision --autogenerate -m "our message tag"
```
- this will start our `app` service, and run the command we want


> Note this runs the migration **within** the container, but since we want these changes to reflect within our local machine we need to link our local machine to the container. Which can be completed by modifying the docker compose yml as follows


``` 
services:
  <<service_name>>: # our service is app
    volumes:
      - <<local_path>>:<<container_path>> # for us it will be .:/app
```

- this won't work by itself since we need the `postgresql` service to be running. So run `docker compose up -d db` so sqlalchemy can actually connect to the database


#### Issue 1:
- There was an issue with the postgres container not staying up, this was due to a change in how local volumes are supposed to be setup. 
- fix by changing the line in the compose yml
```
volumes:  
- postgres_data:/var/lib/postgresql/data
```
- to
```
volumes:  
- postgres_data:/var/lib/postgresql
```

#### issue 2:
- postgresql couldn't resolve the database name, to fix this we set a new environment variable in it as such matching the name we chose for our database which was just `db`
```
services:
	db:
		environment:
		- POSTGRES_DB=db
```
- must match our database url


## Timestamp Change

since alembic autogenerates using `sa.DateTime()` which won't account for timezones we need to make the changes ourselves, finding each line and updating them with the parameter `timezone=True`


### Ownership issue

Since the container runs as root it creates the migration file as a root user, so we can't actually alter the file as our current user on our local machine.  Some solutions
1. Open the file with a text editor as root 
	1. `sudo vim <<migration_file>>`
2. Change the ownership of the file to the current user
	1. `sudo chown <<new_owner>> <<migration_file>>`
3. We can alter the dockerfile such that when it creates file it creates them as a certain user, will consider it at a later date if the above two become too annoying. 

Now we can run the following command

```
docker compose run app alembic upgrade head
```
- note that the database service must be running and the app service isn't running.


### Check the changes

with both containers (db and app) run the following

```
docker compose exec db psql -U <<username>> -d <<database_name>>
```
- `docker compose exec` runs a command in an already running container
- `db` our container containing our database server
- `psql` opens postgres interactive shell
- `-U <<username>>` connect as a user
- `-d <<connect to a database>>`
- username and database name can be found in our docker compose yml

running `\dt` we can see our tables

```
db=# \dt
                   List of tables
 Schema |      Name       | Type  |      Owner      
--------+-----------------+-------+-----------------
 public | alembic_version | table | supersecretname
 public | check_result    | table | supersecretname
 public | endpoint_target | table | supersecretname
(3 rows)
db=# 
```



