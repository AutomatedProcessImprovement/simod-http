#!/usr/bin/env bash

# Takes users, spawn-rate, and run-time from CLI args
# Defaults to 100, 10, 10s
users=${1:-100}
spawn_rate=${2:-10}
run_time=${3:-10s}

# Output directory
timestamp=$(date +%Y%m%d%H%M%S)
output_dir="results/$timestamp"
mkdir -p "$output_dir"

# Experiment
poetry run locust \
--host $SIMOD_HTTP_URL \
--users $users \
--spawn-rate $spawn_rate \
--run-time $run_time \
--headless \
--csv $output_dir/simod-http \
--logfile $output_dir/locust.log \
--loglevel INFO \
--html $output_dir/report.html
