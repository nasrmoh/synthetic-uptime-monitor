
## Learning Redis: commands first, then the Python wrapper

We'll see what Redis does at the command level first. We verify manually with `redis-cli` and then look at how `redis-py` exposes the same commands as Python methods. `redis-py` follows the official Redis command syntax closely. 


### Part 1 : Keys and Basic String Values

The commands we start with are `PING`, `SET`, `GET`, `DEL`, `EXISTS`. To run them manually we run the following against our already running compose stack

```
docker compose exec redis redis-cli
```

Then inside of `redis-cli`:

``` redis
PING
SET scratch:status up
GET scratch:status
EXISTS scratch:status
DEL scratch:status
GET scratch:status
```

`SET` creates or replaces a key
`GET` returns the string value
`GET` returns `nil` when the key doesn't exist, not an error, its expected outcome
`GET` errors if the key holds a non-string Redis data type


This links back to our key shape
`target:<<target_id>>:last_status`


### Part 2: Expiration

Now `EXPIRE` and `TTL`

```redis
SET scratch:status up
EXPIRE scratch:status 30
TTL scratch:status
GET scratch:status
```

Then we wait a few seconds and check again

```redis
TTL scratch:status
GET scratch:status
```

![[Pasted image 20260711054608.png]]
- `TTL` first returns 23, and then returns -2, and once expired `GET` returns `nil`

`TTL` returns different things:
- Positive number for the remaining seconds until expiration (24 means 24 seconds left)
- `-1` this implies that the key isn't set to expire
- `-2` the key doesn't exist
	- it either was never set or expired

We can set the value and expiry together in one call:

```
SET scratch:status up EX 30
```

Which is equivalent to the following Python pattern

```python
rd.set(key, value, ex=30)
```

Better to use the combined command



### Part 3: Testing the Actual Cache Shape

Let's experiment.

```redis
SET target:1:last_status up EX 60
GET target:1:last_status
TTL target:1:last_status
```


```redis
SET target:1:last_status down EX 60
GET target:1:last_status
TTL target:1:last_status
```

Old value is replaced completely. Which is what we want for "latest status". 


### String or Hash?

We'll start with a string as we only really need one status value (or one JSON blob containing the few fields).

```redis
SET target:1:last_status up EX 60
```

A Redis hash is useful if we want several related fields addressable


```redis
HSET target:1:last_check status up status_code 200 latency_ms 42 checked_at 2026-05-30T10:15:00Z
```

Then to read individual fields or all of them together:

```redis
HGET target:1:last_check status
HGETALL target:1:last_check
```



`HSET` creates / updates fields within a has. But `EXPIRE` on a hash applies to the whole key, not per-field. 

We won't be using a Hash. A single JSON string containing the summary results (`status_code`, `error_class`, `latency_ms`, `checked_at`) is enough. 

### Part 4: mapping the commands to `redis-py`


Connecting:

```redis
r = redis.Redis(host="Localhost", port=6739, decode_response=True)
```
`decode_response` makes string responses come back as actual Python strings instead of using raw bytes. This project uses `from_url()` reading from our environment variable `REDIS_URL`. But it does the same thing

The exact command-to-method mapping

|Redis command|redis-py method|
|---|---|
|`PING`|`rd.ping()`|
|`SET key value`|`rd.set(key, value)`|
|`GET key`|`rd.get(key)`|
|`DEL key`|`rd.delete(key)`|
|`EXISTS key`|`rd.exists(key)`|
|`EXPIRE key 60`|`rd.expire(key, 60)`|
|`TTL key`|`rd.ttl(key)`|
|`HSET`|`rd.hset(...)`|
|`HGETALL`|`rd.hgetall(...)`|


## Why the Colons in the Key Name?

Redis doesn't treat `:` as anything special. a key like `target:1:last_status` is to Redis a flat string, no different from `target1laststatus`. Colon separate is a community convention. Sort of acts like a `/` so it could read like a folder structure `target/1/last_status`

we use specifically `target:<<target_id>>:last_status` because it reads simply like. "The last status field for targets with an id of `target_id`"

