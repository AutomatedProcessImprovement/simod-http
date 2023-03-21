import os
import random
from pathlib import Path

from locust import task, FastHttpUser


class User(FastHttpUser):
    host = os.environ.get('SIMOD_HTTP_URL')
    endpoint_url = f'{host}/discoveries'
    assets_dir = Path('./assets')

    def wait_time(self):
        return random.expovariate(1 / 60)

    @task
    def post1(self):
        self.make_post()

    @task
    def post2(self):
        self.make_post()

    @task
    def post3(self):
        self.make_post()

    @task
    def post4(self):
        self.make_post()

    @task
    def post5(self):
        self.make_post()

    @task
    def post6(self):
        self.make_post()

    @task
    def post7(self):
        self.make_post()

    @task
    def post8(self):
        self.make_post()

    @task
    def post9(self):
        self.make_post()

    @task
    def post10(self):
        self.make_post()

    def make_post(self):
        configuration_path = self.assets_dir / 'sample.yaml'
        event_log_path = self.assets_dir / 'PurchasingExample.xes'

        data = {
            'configuration': ('configuration.yaml', configuration_path.open('rb'), 'text/yaml'),
            'event_log': ('event_log.xes', event_log_path.open('rb'), 'application/xml'),
        }

        content_type = 'multipart/form-data'

        self.client.post(
            self.endpoint_url,
            headers={'Content-Type': content_type},
            files=data,
        )
