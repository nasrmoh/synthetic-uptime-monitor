#!/bin/bash

# Export every variable defined by .env into this shell's environment,
# rather than just assigning them locally. Without "set -a", the
# variables would exist in this script but NOT be visible to the
# docker compose subprocess below.
set -a
source .env
set +a  # turn off auto-export so nothing else leaks into the environment unintentionally

# Drop into the Postgres terminal (psql) inside the running db container.
# Usage: ./database-terminal.sh        -> connects to the main app database
#        ./database-terminal.sh TEST   -> connects to the test database instead
#
# This exists because reaching into the db container's psql shell manually
# means remembering the container name, the -U flag, and the db name every
# time. This script encodes that once.
if [[ "$1" == "TEST" ]]; then
    docker compose exec db psql \
        -U "$POSTGRES_USER" \
        -d "$TEST_DATABASE_NAME"
else
    docker compose exec db psql \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB"
fi