# synthetic-uptime-monitor

## Current Status

- week 0
  - `/health` and `/ready` endpoints setup. Project structure setup. Pytest function testing these endpoints setup. 

## Architecture Vision
- A synthetic uptime monitor which sends HTTP requests to a list of some target URLs then records the response time and status codes, which will be stored in a PostgreSQL database. Redis is used to hold short lived operational states, for example the last known target status. 
The metrics will be exposed via Prometheus, visualized using Grafana, and finally routed using Alertmanager

## Architcture Diagram 
- To be Added

## Technology Rationale
- FastAPI over Django:
  - I wanted to use a pure JSON API, Django is a "batteries-included" framework, it provides things like HTML templates, admin dashboard and ORM that I didn't really think were necessary here. Something lighter like FastAPI was more important to me
- PostgreSQL:
  - Persistent storage
- Redis:
  - I wanted a form of fast in-memory caching that's safe to rebuild from if something happens to Postgres   
- Promethues + Grafana + Alertmanager:
  -  I wanted to learn the standard observability stack where metrics were collected, visualized and alerts were routed as a separate concern
- Docker + Compose:
  - I wanted something that would work in multiple different environments, and a system to easily run everything.


## Docker Run Instructions

> Ensure that Docker Desktop is running first

To run the project using docker execute the following commands

Build the images first:
```bash
docker compose build
```

Next run all services:
``` bash
docker compose up
```

or in a single command to build and run all images:

```bash
docker compose up --build
```


Once the containers are running you can access the services here:

- Application: http://localhost:8000



## Useful Commands For Viewing Logs in Docker Compose

View the logs for all our services:
``` bash
docker compose logs
```

View logs for a specific service:

``` bash
docker compose logs <<service-name>>
```
- Note the service name is outlined in the `docker-compose.yml` file


View logs in real time:
```bash
docker compose logs -f <<service-name>>
```

View only the last `10` lines:

```bash
docker compose logs --tail=10
```

Most useful, Show the last `10` lines in real time for a given service:

```bash
docker compose logs -f --tail=10 <<service-name>> 
```
