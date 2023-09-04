#!/usr/bin/env bash

template="compose-template.yaml"
development_output="compose.yaml"

simod_version=$(poetry version -s)
simod_http_image_name="nokal/simod-http:$simod_version"
simod_http_worker_image_name="nokal/simod-http-worker:$simod_version"
simod_http_scheduler_image_name="nokal/simod-http-scheduler:$simod_version"
simod_http_env_file_name_dev=".simod-http.env.dev"

sed -e "s|<simod-http-image-name>|$simod_http_image_name|g" \
    -e "s|<simod-http-worker-image-name>|$simod_http_worker_image_name|g" \
    -e "s|<simod-http-scheduler-image-name>|$simod_http_scheduler_image_name|g" \
    -e "s|<simod-http-env-filename>|$simod_http_env_file_name_dev|g" \
    $template > $development_output
