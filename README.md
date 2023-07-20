# Simod HTTP

![simod-http](https://github.com/AutomatedProcessImprovement/simod-http/actions/workflows/build.yaml/badge.svg)
![version](https://img.shields.io/github/v/tag/AutomatedProcessImprovement/simod-http)

Simod HTTP is a collection of services to run Simod in a distributed environment ready for deployment using Docker. It extends [Simod](https://github.com/AutomatedProcessImprovement/Simod) with an HTTP API and task management using Celery (RabbitMQ and Redis).

## Getting Started

```bash
docker compose up --build
```

After the services are up and running, you can access the following services:

* The HTTP API is available at http://localhost:8000/v1/ with the specification at http://localhost:8000/docs and http://localhost:8000/redoc. 
* The Celery Flower dashboard is available at http://localhost:5555.

To fetch discoveries, run:

```bash
curl -X GET "http://localhost:8000/v1/discoveries" -H  "accept: application/json"
```

To create a discovery, run a Python script instead, because submitting a discovery requires two file uploads with a boundary in the request header and body, which is easier done in Python:

```bash
poetry run python tests/post_request.py
```

If the project is not installed yet, run:

```bash
pip install poetry
poetry install
```