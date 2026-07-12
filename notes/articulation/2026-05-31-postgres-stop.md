
`/ready` works then we run the command `docker compose stop db` and check our ready endpoint again via `curl -i localhost:8000/ready` and this is the log result

```
HTTP/1.1 503 Service Unavailable
date: Sat, 11 Jul 2026 22:17:11 GMT
server: uvicorn
content-length: 69
content-type: application/json

{"status":"unavailable","dependencies":{"db":"down","redis":"ready"}}
```

`docker compose logs app --tail 5`

```
app-1  | INFO:     Waiting for application startup.
app-1  | INFO:     Application startup complete.
app-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
app-1  | INFO:     172.19.0.1:43918 - "GET /ready HTTP/1.1" 200 OK
app-1  | INFO:     172.19.0.1:40830 - "GET /ready HTTP/1.1" 503 Service Unavailable
```

Then we start the database again via `dockeer compose start db`  check the endpoint via `curl -i localhost:8000/ready` and check the log result

```
HTTP/1.1 200 OK
date: Sat, 11 Jul 2026 22:17:53 GMT
server: uvicorn
content-length: 61
content-type: application/json

{"status":"ok","dependencies":{"db":"ready","redis":"ready"}}
```

`docker compose logs app --tail 5`
```
app-1  | INFO:     Application startup complete.
app-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
app-1  | INFO:     172.19.0.1:43918 - "GET /ready HTTP/1.1" 200 OK
app-1  | INFO:     172.19.0.1:40830 - "GET /ready HTTP/1.1" 503 Service Unavailable
app-1  | INFO:     172.19.0.1:44740 - "GET /ready HTTP/1.1" 200 OK
```

So recovery is working.


## What is the difference between service liveness and dependency readiness?

The main difference is that service liveness refers to whether our main service (the app) is actually running and able to respond to requests. All we need to do for liveness is determine if the process is running. But just because the application is "live" doesn't mean that it is actually ready to serve traffic (say some users). That depends on whether or not the dependencies (Postgres & Redis) are ready. If all dependencies are live and are able to communicate to our app, we can say it is "ready" that is it is able to do useful work now.  




