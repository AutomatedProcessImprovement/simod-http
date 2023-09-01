# Simod HTTP

![build](https://github.com/AutomatedProcessImprovement/simod-http/actions/workflows/build.yaml/badge.svg)
![deploy](https://github.com/AutomatedProcessImprovement/simod-http/actions/workflows/deploy.yaml/badge.svg)
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
curl -X GET "http://localhost:8000/api/v1/discoveries"
```

To create a discovery, submit at least an event log file:

```bash
curl -X POST "http://localhost:8000/api/v1/discoveries/" -H "content-type: multipart/form-data" -F event_log=@./tests/assets/AcademicCredentials_train.csv 
```

To provide your own configuration, add a configuration file to the request too:

```bash
curl -X POST "http://localhost:8000/api/v1/discoveries/" -H "content-type: multipart/form-data" -F event_log=@./tests/assets/AcademicCredentials_train.csv -F configuration=@./tests/assets/sample.yaml
```

To install the project locally, run:

```bash
# with poetry
pip install poetry
poetry install

# or without poetry
pip install -r requirements.txt
pip install .
```

## Managed Simod HTTP instance

The managed instance is most likely running (no uptime guarantees 🫣) at http://simod.cloud.ut.ee/api/v1/. 

Check the API documentation at [http://simod.cloud.ut.ee/api/v1/docs](http://simod.cloud.ut.ee/api/v1/docs) or [http://simod.cloud.ut.ee/api/v1/redoc](http://simod.cloud.ut.ee/api/v1/redoc) for more information.

## Deployment

See [Configuration management with Ansible](ansible/README.md).

Single-button deployment can be triggered from the [GitHub Actions workflow]((https://github.com/AutomatedProcessImprovement/simod-http/actions/workflows/deploy.yaml)). Celery Flower dashboard is accessible at https://simod.cloud.ut.ee/flower.