FROM python:3.9-bullseye

RUN pip install --upgrade pip poetry

WORKDIR /usr/src/simod-http
ADD . .
RUN poetry install

WORKDIR /usr/src/simod-http/tests

ENV PYTHONUNBUFFERED=1

EXPOSE 8089

CMD ["poetry", "run", "locust", "--master"]
