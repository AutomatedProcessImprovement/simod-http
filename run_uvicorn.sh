#!/usr/bin/env bash

env
poetry run uvicorn --host $SIMOD_HTTP_HOST --port $SIMOD_HTTP_PORT --log-level $SIMOD_HTTP_LOG_LEVEL --access-log simod_http.main:api