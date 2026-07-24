#!/bin/bash

if [[ -z "$1" ]]; then
  echo "usage: ./redis-last-status.sh <<target_id>>"
  exit 1
fi



if [[ $1 =~ ^[0-9]+$ ]]; then
  docker compose exec redis redis-cli GET "target:$1:last_status" | jq
  else
    echo "Error: target_id must be a number"
    echo "usage: ./redis-last-status.sh <<target_id>>"
    exit 1
fi