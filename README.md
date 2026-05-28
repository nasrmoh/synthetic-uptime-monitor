# synthetic-uptime-monitor

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
