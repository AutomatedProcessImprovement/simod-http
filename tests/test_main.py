from pathlib import Path

from httpx import Response
from requests_toolbelt import MultipartEncoder
from starlette.testclient import TestClient

from simod_http.app import RequestStatus
from simod_http.main import api


class TestAPI:
    client = TestClient(api)
    assets_dir = Path('./assets')
    configuration_path = assets_dir / 'sample.yaml'
    event_log_path = assets_dir / 'PurchasingExample.xes'

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
            'archive_url': None,
            'error': {'detail': None, 'message': 'Request not found'},
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

    def post_discovery(self) -> Response:
        data = MultipartEncoder(
            fields={
                'configuration': ('configuration.yaml', self.configuration_path.open('rb'), 'text/yaml'),
                'event_log': ('event_log.xes', self.event_log_path.open('rb'), 'application/xml'),
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

    def test_discoveries_file(self):
        response = self.post_discovery()
        request_id = response.json()['request_id']

        archive_file = f'{request_id}.tar.gz'
        response = self.client.get(f'/discoveries/{request_id}/{archive_file}')

        assert response.status_code == 404
        assert response.json() == {
            'archive_url': None,
            'error': {'detail': None, 'message': f'File not found: {archive_file}'},
            'request_id': request_id,
            'request_status': RequestStatus.FAILED.value,
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
            'archive_url': None,
            'error': None,
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
            'archive_url': None,
            'error': None,
        }
