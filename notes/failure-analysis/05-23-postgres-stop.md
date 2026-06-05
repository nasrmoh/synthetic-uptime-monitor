What happened?
- We stopped the `db` container which sort of emulates the "service" being down and then tried to reach the `/ready` endpoint
- We got this response `{"status":"ok","dependencies":{"db":"pending","redis":"pending"}`


Where it logged?
- we can see the log from the `app` container using the following command
- `docker compose logs app --tail=1`
- with result `app-1  | INFO:     172.19.0.1:39276 - "GET /ready HTTP/1.1" 200 OK`
- Which makes sense we haven't yet updated the `/ready` endpoint to alter depending on the status of our `db` service

What We'd Change so `/ready` returns 503 cleanly
- We would try to connect to the database or to redis
- if both of these succeed we would return `200`
- if either fails we would return `503` with a response body that indicates which is down
- this can be done with a simple query in PostgreSQL  or a simple operation in Redis