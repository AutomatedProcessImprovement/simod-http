FROM nokal/simod:3.5.24 as base

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /usr/src/simod-http

# Download dependencies as a separate step to take advantage of Docker's caching.
# Leverage a cache mount to /root/.cache/pip to speed up subsequent builds.
# Leverage a bind mount to requirements.txt to avoid having to copy them into
# into this layer.
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python3 -m pip install -r requirements.txt

# Copy the source code into the container.
COPY . .

# Expose the port that the application listens on.
EXPOSE $SIMOD_HTTP_PORT

# Run the application.
CMD uvicorn 'simod_http.main:api' --host=$SIMOD_HTTP_HOST --port=$SIMOD_HTTP_PORT --workers=$WEB_CONCURRENCY --log-level=$SIMOD_LOGGING_LEVEL --proxy-headers
