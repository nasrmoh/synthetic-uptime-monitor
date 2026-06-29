# synthetic-uptime-monitor

## What is a Synthetic Uptime Monitor

A synthetic uptime monitor is a service which generates periodic HTTP requests to target services. It then records observations on whether the service could be reached and how the service responded to our request. These observations are used to measure the services availability and its performance over time. 

### What is Uptime?

*Uptime* is a measure of *availability*, generally measured as a percentage over some base unit of time. If our base unit is 1 day with 24 hours, and our service, say a website is down for 48 minutes, then we'd have about `23 hours, 12 minutes` which comes to `(23 + 12/60) / 24 = 96.67% uptime`. Or if it is down for 4 hours out of an entire month then `(716/720) * 100 = 99.44% uptime` 


### What is an Uptime Monitor?

This is a service/application whose job is to determine if a service is up/available, It checks repeatedly and from these checks it can determine the following
- uptime percentage
- outage duration
- average latency
- failure count

> Note that an uptime monitor records observations and from that determines the uptime (and associated data)


### What does the Synthetic Part Refer to?

This refers to *synthetically* generating traffic, that is requests that imitate real users. For example the monitor could do something like `GET https://google.com/health` 


### Why Even Do This?

Since we'd like to know when a application / service is down we could just wait until a user experiences a failure but that would degrade user experience, so instead by generating synthetic traffic we can more readily check when our services are down. If a website is down during low traffic and we used only user input to determine this then it could take hours before a real user notices and reports the issue. By using synthetic monitoring we can know about problems before they reach our users.


### So Really What is it Doing?

Every few seconds send an HTTP request, measure the status code, the latency, the error class (if there was an error) and the time of the request, store this information and repeat.

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

1. Copy in `.env.example` file into `.env` and add secrets.

To run the project using docker execute the following commands

2. Build images and run containers:
```bash
docker compose up --build
```
- Note this will fill the terminal with the compose output, include the flag -d to run in detached mode

Once all containers are operational and can communicate with each other:

3. Complete migrations by using the following command
```
docker compose run app alembic upgrade head
```


4. You can access the application here: http://localhost:8000


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
