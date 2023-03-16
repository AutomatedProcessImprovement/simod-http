#!/usr/bin/env bash

poetry run gunicorn simod_http.main:api -w $SIMOD_GUNICORN_WORKERS -k uvicorn.workers.UvicornWorker