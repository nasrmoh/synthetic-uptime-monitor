#!/bin/bash

set -a
source .env
set +a

if [[ "$1" == "TEST" ]]; then
    docker compose exec db psql \
        -U "$POSTGRES_USER" \
        -d "$TEST_DATABASE_NAME"
else
    docker compose exec db psql \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB"
fi