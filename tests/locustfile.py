from pathlib import Path

from locust import HttpUser, task
from requests_toolbelt import MultipartEncoder


class User(HttpUser):
    endpoint_url = 'http://localhost:8000/discoveries'
    assets_dir = Path('./assets')

    @task
    def post(self):
        configuration_path = self.assets_dir / 'sample.yaml'
        event_log_path = self.assets_dir / 'PurchasingExample.xes'

        data = MultipartEncoder(
            fields={
                'configuration': ('configuration.yaml', configuration_path.open('rb'), 'text/yaml'),
                'event_log': ('event_log.xes', event_log_path.open('rb'), 'application/xml'),
            }
        )

        self.client.post(
            self.endpoint_url,
            headers={"Content-Type": data.content_type},
            data=data,
        )
