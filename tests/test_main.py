from pathlib import Path
from unittest.mock import MagicMock

from fastapi import FastAPI
from httpx import Response
from pika import BlockingConnection
from requests_toolbelt import MultipartEncoder
from starlette.testclient import TestClient

from simod_http.requests import RequestStatus
from simod_http.broker_client import BrokerClient
from simod_http.main import api


def stub_broker_client() -> BrokerClient:
    channel = MagicMock()
    connection = MagicMock(spec=BlockingConnection)
    connection.channel.return_value = channel
    client = BrokerClient('', '', '', connection=connection)
    client.publish_request = MagicMock()
    client.connect = MagicMock()
    return client


def inject_broker_client(api: FastAPI, client: BrokerClient) -> FastAPI:
    api.state.app.broker_client = client
    return api


def path_to_current_file_dir() -> Path:
    return Path(__file__).parent


class TestAPI:
    client = TestClient(inject_broker_client(api, stub_broker_client()))

    def test_root(self):
        response = self.client.get('/')
        assert response.status_code == 404
        assert response.json() == {
            'error': {'message': 'Not Found'},
        }

    def test_discoveries(self):
        response = self.client.get('/discoveries/123')
        assert response.status_code == 404
        assert response.json() == {
            'request_id': '123',
            'request_status': RequestStatus.UNKNOWN.value,
            'error': {'message': 'Request not found'},
        }

    def test_discoveries_patch(self):
        response = self.client.patch('/discoveries/123')
        assert response.status_code == 422
        assert response.json() == {
            'error': {
                'message': 'Validation error',
                'detail': [
                    {
                        'loc': ['body'],
                        'msg': 'field required',
                        'type': 'value_error.missing',
                    }
                ]
            }
        }

    def test_discoveries_post(self):
        response = self.post_discovery()

        assert response.status_code == 202
        assert 'request_id' in response.json()

        self.delete_discovery(response.json()['request_id'])

    def test_discoveries_file(self):
        response = self.post_discovery()
        request_id = response.json()['request_id']

        archive_file = f'{request_id}.tar.gz'
        response = self.client.get(f'/discoveries/{request_id}/{archive_file}')

        assert response.status_code == 404
        assert response.json() == {
            'error': {'message': f'File not found: {archive_file}'},
            'request_id': request_id,
            'request_status': RequestStatus.PENDING.value,
        }

        self.delete_discovery(response.json()['request_id'])

    def test_discoveries_file_patch(self):
        response = self.post_discovery()
        app_response = response.json()
        request_id = app_response['request_id']
        assert app_response['request_status'] == RequestStatus.ACCEPTED.value

        response = self.client.patch(f'/discoveries/{request_id}', json={'status': RequestStatus.PENDING})

        assert response.status_code == 200
        assert response.json() == {
            'request_id': request_id,
            'request_status': RequestStatus.PENDING.value,
        }

        self.delete_discovery(response.json()['request_id'])

    def test_discoveries_delete(self):
        response = self.post_discovery()
        request_id = response.json()['request_id']

        response = self.client.delete(f'/discoveries/{request_id}')

        assert response.status_code == 200
        assert response.json() == {
            'request_id': request_id,
            'request_status': RequestStatus.DELETED.value,
        }

    def post_discovery(self) -> Response:
        assets_dir = path_to_current_file_dir() / 'assets'
        configuration_path = assets_dir / 'sample.yaml'
        event_log_path = assets_dir / 'PurchasingExample.xes'

        data = MultipartEncoder(
            fields={
                'configuration': ('configuration.yaml', configuration_path.open('rb'), 'text/yaml'),
                'event_log': ('event_log.xes', event_log_path.open('rb'), 'application/xml'),
            }
        )

        response = self.client.post(
            '/discoveries',
            headers={"Content-Type": data.content_type},
            content=data.to_string(),
        )

        return response

    def delete_discovery(self, request_id: str) -> Response:
        response = self.client.delete(f'/discoveries/{request_id}')
        return response
