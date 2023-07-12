# Simod HTTP

![simod-http](https://github.com/AutomatedProcessImprovement/simod-http/actions/workflows/simod-http-build.yaml/badge.svg)
![version](https://img.shields.io/github/v/tag/AutomatedProcessImprovement/simod-http)

Simod HTTP is a web server for Simod. It provides a REST API for Simod job requests management. A user submits a request to Simod HTTP by providing a configuration file, an event log (BPMN model and test log are not supported yet). 

Simod HTTP then accepts the request, save input files and puts a task into a queue. Another service, Simod Queue Worker, is responsible for processing the task from the queue.

After the task is processed, Simod HTTP notifies the user about the result of the job if a callback URL has been provided in the initial request. Otherwise, the user can check the status of the job by sending a request to Simod HTTP.

To start with the web service with Docker, run:

```shell
docker run -it -p 8080:8080 nokal/simod-http:0.2.0
```

This gives you access to the web service at `http://localhost:8080`. The OpenAPI specification is available
at `http://localhost:8080/docs`.

### Example requests

Submitting a job with a configuration and an event log in using a `multipart/form-data` request:

```shell
curl -X POST "http://localhost:8080/discoveries" \
-F "configuration=@resources/config/sample.yml; type=application/yaml" \
-F "event_log=@resources/event_logs/PurchasingExample.csv; type=text/csv"
```

`resources/config/sample.yml` is the path to the configuration file and `resources/event_logs/PurchasingExample.csv` is
the path to the event log. The type of the files better be specified.

To check the status of the job, you can use the following command:

```shell
curl -X GET "http://localhost:8080/discoveries/85dee0e3-9614-4c6e-addc-8d126fbc5829"
```

Because a single job can take a long time to complete, you can also provide a callback HTTP endpoint for Simod HTTP to
call when the job is ready. The request would look like this:

```shell
curl -X POST "http://localhost:8080/discoveries?callback_url=http//youdomain.com/callback" \
-F "configuration=@resources/config/sample.yml; type=application/yaml" \
-F "event_log=@resources/event_logs/PurchasingExample.csv; type=text/csv"
```
