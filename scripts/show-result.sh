#!/bin/bash

curl -s -X GET http://localhost:8000/targets/$1/results | jq