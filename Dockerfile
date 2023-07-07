FROM python:3.9-bullseye

RUN pip install --upgrade pip poetry

WORKDIR /usr/src/simod-http
ADD . .
RUN poetry install

ENV PYTHONUNBUFFERED=1

EXPOSE $SIMOD_HTTP_PORT

CMD ["bash", "run.sh"]
