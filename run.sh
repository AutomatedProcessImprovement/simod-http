#!/usr/bin/env bash

poetry run uvicorn simod_http.main:api --host $SIMOD_HTTP_HOST --port $SIMOD_HTTP_PORT --log-level $SIMOD_HTTP_LOG_LEVEL