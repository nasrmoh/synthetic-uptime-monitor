

## Request Path

the basic deployment path is

Client -> VM:80 -> nginx -> Uvicorn:8000 -> FastAPI

nginx serves as a *public entry point* to the application

So FastAPI still runs through Uvicorn on port 8000, but that port doesn't need to be exposed to the public internet. `nginx` receives the public request and forwards it internally to FastAPI


This gives the simple boundary:

```
Internet -> nginx -> FastAPI
```

Instead of:

```
Internet -> FastAPI
```

## `listen`

`listen` tells nginx which port to accept connections on


for example:

```
listen 80;
```

means nginx will accept http connections on port 80.

this describes only where nginx receives traffic from. It says nothing about where FastAPI  is running.

so `listen` serves as the public entrance for nginx


## `server`

this block describes the configuration for a particular virtual web server

```yaml
server {
	listen 80;
}
```


the server block sets up the rules for a particular website / application



## `location`

Inside a `server` block, `location` determines how nginx handles requests based on their URI

for example

```
locaiton / {
	...
}
```

matches requests under `/`.

that includes things like

```
/health
/ready
/targets
/metrics
```


so 
- `server` = which application / site
- `location` = which path inside of that application / site




## `proxy_pass`

`proxy_pass` tells nginx *where to forward the request*

this is what makes nginx act as a reverse proxy


so:

```
location / {
	proxy_pass http://<FastAPI upstream>;
}
```

the request flow becomes:

```
Client -> nginx
nginx -> FastAPI
```


these are two separate connections. The client never directly connects to FastAPI

nginx accepts the client's request, opens its own connection to the upstream FastAPI server, receives FastAPI's response, and then sends that response back to the client


# Forwarded Headers


Because nginx sits between the client and FastAPI, FastAPI may otherwise see nginx as the source of the request.

Forwarded headers allow nginx to preserve some of the information about the original request


the main ones we should know are:

```
Host
X-Real-IP
X-Forwarded-For
X-Forwarded-Proto
```

## `Host`

This preserves the hostname requested by the client.

for example:
```
monitor.example.com
```

## `X-Real-IP`

Passes along the original client's IP address.


## `X-Forwarded-For`

Records the client IP and potentially the chain of proxies that the request travelled  through.

## `X-Forwarded-Proto`


Preserves whether the original client connected using:

`http` or `https`





# Testing Configuration

Changing the nginx configuration does not automatically mean nginx is successfully using the new configuration.

before applying a new configuration change we should test it 

```
nginx -t
```


so our workflow should be

1. edit configuration
2. `nginx -t`
3. fix any errors we find
4. reload nginx