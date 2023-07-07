#!/usr/bin/env bash

env
poetry run gunicorn simod_http.main:api -k uvicorn.workers.UvicornWorker -w $SIMOD_GUNICORN_WORKERS -b $SIMOD_HTTP_ADDRESS --log-level $SIMOD_LOGGING_LEVEL