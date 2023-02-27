FROM python:3.9-bullseye

RUN pip install --upgrade pip poetry

WORKDIR /usr/src/simod-http
ADD . .
RUN poetry install

ENV SIMOD_HTTP_DEBUG=false
ENV SIMOD_HTTP_HOST=0.0.0.0
ENV SIMOD_HTTP_PORT=8080
ENV SIMOD_HTTP_SCHEME=http
ENV SIMOD_HTTP_STORAGE_PATH=./data
ENV SIMOD_HTTP_LOGGING_LEVEL=debug
ENV SIMOD_HTTP_REQUEST_EXPIRATION_TIMEDELTA=604800
ENV SIMOD_HTTP_STORAGE_CLEANING_TIMEDELTA=300
ENV SIMOD_HTTP_SMTP_SERVER=localhost
ENV SIMOD_HTTP_SMTP_PORT=2500
ENV SIMOD_REQUESTS_QUEUE_NAME=requests
ENV SIMOD_RESULTS_QUEUE_NAME=results
ENV BROKER_URL=amqp://guest:guest@localhost:5672

EXPOSE $SIMOD_HTTP_PORT

CMD ["bash", "run.sh"]
