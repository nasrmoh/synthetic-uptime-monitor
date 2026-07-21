#!/bin/bash

curl -X GET http://localhost:8000/targets/$1/results | jq