#!/usr/bin/env bash

docker build -t nokal/simod-http:$(poetry version -s) -f http.dockerfile .