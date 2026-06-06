#!/bin/bash
printf "==== /health endpoint====\n"
curl localhost:8000/health
printf "\n====/ready endpoint====\n"
curl localhost:8000/ready
printf "\n==== docker containers check====\n"
docker compose ps
printf "\n"