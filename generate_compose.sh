#!/usr/bin/env bash

# This script generates compose.yaml manifests for production deployment and development.

production_template="compose-production-template.yaml"
production_output="ansible/compose.yaml"

development_template="compose-development-template.yaml"
development_output="compose.yaml"

simod_version=$(poetry version -s)
simod_http_image_name="nokal/simod-http:$simod_version"
simod_http_worker_image_name="nokal/simod-http-worker:$simod_version"

sed -e "s|<simod-http-image-name>|$simod_http_image_name|g" \
    -e "s|<simod-http-worker-image-name>|$simod_http_worker_image_name|g" \
    $production_template > $production_output

sed -e "s|<simod-http-image-name>|$simod_http_image_name|g" \
    -e "s|<simod-http-worker-image-name>|$simod_http_worker_image_name|g" \
    $development_template > $development_output