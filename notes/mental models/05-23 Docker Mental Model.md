## Containers vs Virtual Machines

#### Containers
Containers are isolated linux processes. They have their own view of files, networking and running processes, but they share the host machine's kernel. By default a container cannot see its host's filesystem or even other processes beyond its scope unless these things are shared by the Host. Since a container doesn't have its own kernel nor does it require booting up on OS they tend to be quick to start up and are usually megabytes in size. 


#### Virtual Machines

Virtual machines emulate an entire computer. Each instance of a virtual machine runs its own operating system and kernel on top of virtual hardware managed by a hypervisor. From the Guest OS's perspective it has access to its own CPU, memory, and storage. As virtual machines require a full OS to boot up they tend to be "heavyweight" taking some time to spin up and measuring in gigabytes of size. 


#### Key Difference

```
Container
	its own view of processes/files/network
	shares the hosts kernel

Virtual Machines
	Its own processes/files/netowrk
	its own kernel
```




## Image Layer Caching


Docker images are built layer by layer from one instruction at a time. Docker caches each layer and checks if anything has changed from the last build. If a given layer hasn't changed docker uses the cached version. If a layer has changed, docker will rebuild it and then rebuild every layer afterwards. 

So the order of instruction in a Dockerfile matters. We place stable things at the top of the file and variable things at the bottom. 

For example from our project:

``` Dockerfile
Copy requirements.txt                # Stable 
RUN pip install -r requirements.txt  # Stable
COPY . .                             # Constantly Changes. Goes to the bottom
```

If we were to put `COPY . .` at the top any changes in our source could would differ from Docker's cached version and would require it to reinstall all dependencies even if they haven't changed. By placing `COPY requirement.txt` at the top we make sure that we only ever really run the installing of dependencies if they have changed. 

## Start Order vs Readiness


`depends_on` is a Docker Compose instruction that tells Compose to start a given service before another one. For example our `db` service before the `app` service. But it will only wait for the container to start, not the actual service inside of the container to be *ready* to accept connections. 

An example sequence would look like this:


```
db container starts  # Compose sees this and starts the app container
app container starts # App tries to connect to db 
db not ready         # Still trying to setup
connection fails     # we get crashes or errors  
```

This clearly indicates to us that **start != ready**. Our database takes a bit of time to setup even after the container has started. 

This is why we have two different endpoints in `/health` and `/ready`

- `/health` answers this question
	- *"Is the FastAPI service live?"*
- `/ready` answers this question
	- *"Is the FastAPI and all its dependencies ready to serve traffic?"*

This is why we have retry loops in place. So instead of the application crashing and burning on a single (or many) failed connections it will retry to establish a connection until the dependency is ready.


## Compose Internal DNS and the Localhost Trap

For a given stack Docker Compose creates a bridge network between its containers. Compose also creates DNS entries that map service names (like `app`, `db` and `redis`) to the IP addresses  of their containers so that services within the container stack can reach each other by these entries / names.

Say we are inside the app container:
```
db:5432    # This is our PostgreSQL container
redis:6379 # This is our Redis container
```
This is why our environment variables use these service names:

```
DATABASE_URL=postgresql://user:pass@db:5432/mydb
REDIS_URL=redis://redis:6379
```


### The Localhost Trap


When moving from local development to Docker one would think that continuing to use  `localhost` would work to connect the app to the other services like this:

``` yaml
DATABASE_URL=postgresql://user:pass@localhost:5432/mydb
```

This doesn't work because every container has its own network namespace. So within the app container `localhost` refers to the app container itself, not our laptop nor the database container. 

- Container A -> localhost -> Container A itself
- Container B -> localhost -> Container B itself
- Container C -> localhost -> Container C itself

Since there is no PostgreSQL service within the app container, the connection fails

#### `0.0.0.0` Aside


by default, a server listening on `127.0.0.1` only accepts connections coming from the same network namespace. So in a container this means processes running in that container can connect to it. By passing `--host 0.0.0.0` we can tell uvicorn to listen on all network interfaces, which will let connections from outside the container to reach it via Docker's port mappings. 




