# Simod HTTP

Simod HTTP is a web server for Simod. It provides a REST API for Simod and job management. A user submits a request to Simod HTTP by providing a configuration file, an event log, an optionally a BPMN model. Simod HTTP then runs Simod on the provided data and notifies the user when the job is finished because Simod can take a long time to run depending on the size of the event log and the number of optimization trials in the configuration.

Simod HTTP already includes an installed version of Simod in its Docker image. 

To start with the web service, run:

```shell
docker run -it -p 8080:80 nokal/simod-http:v3.2.0
```

This gives you access to the web service at `http://localhost:8080`. The OpenAPI specification is available at `http://localhost:8080/docs`.

### Example requests

Submitting a job with a configuration and an event log in using a `multipart/form-data` request:

```shell
curl -X POST --location "http://localhost:8080/discoveries" \
-F "configuration=@resources/config/sample.yml; type=application/yaml" \
-F "event_log=@resources/event_logs/PurchasingExample.csv; type=text/csv”
```

`resources/config/sample.yml` is the path to the configuration file and `resources/event_logs/PurchasingExample.csv` is the path to the event log. The type of the files better be specified.

To check the status of the job, you can use the following command:

```shell
curl -X GET --location "http://localhost:8080/discoveries/85dee0e3-9614-4c6e-addc-8d126fbc5829"
```

Because a single job can take a long time to complete, you can also provide a callback HTTP endpoint for Simod HTTP to call when the job is ready. The request would look like this:

```shell
curl -X POST --location "http://localhost:8080/discoveries?callback_url=http//youdomain.com/callback" \
-F "configuration=@resources/config/sample.yml; type=application/yaml" \
-F "event_log=@resources/event_logs/PurchasingExample.csv; type=text/csv”
```
