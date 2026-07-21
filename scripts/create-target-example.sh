#!/bin/bash


curl -X POST http://localhost:8000/targets \
    -H "Content-Type: application/json" \
    -d '{
        "url": "www.google.com",
        "method": "GET",
        "interval_seconds": 10,
        "timeout_seconds": 20,
        "failure_threshold": 50,
        "expected_status": 201
    }' \
    -v