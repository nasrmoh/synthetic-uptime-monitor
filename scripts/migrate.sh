#!/bin/bash

# runs migrations for the regular database
docker compose run app alembic upgrade head

# runs migrations for the test database
(
  set -a
  source .env
  set +a
  docker compose run \
    -e DATABASE_NAME="$TEST_DATABASE_NAME"\
    -e DATABASE_URL="$TEST_DATABASE_URL" \
    app alembic upgrade head
)