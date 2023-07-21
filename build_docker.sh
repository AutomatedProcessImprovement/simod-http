#!/usr/bin/env bash

docker build -t nokal/simod-http:$(poetry version -s) -f http.dockerfile .
docker build -t nokal/simod-http-worker:$(poetry version -s) -f worker.dockerfile .