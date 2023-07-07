from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

from bson import ObjectId
from fastapi import FastAPI
from httpx import Response
from pika import BlockingConnection
from requests_toolbelt import MultipartEncoder
from starlette.testclient import TestClient

from simod_http.broker_client import BrokerClient
from simod_http.exceptions import NotFound
from simod_http.main import api
from simod_http.discoveries import DiscoveryStatus, Discovery
from simod_http.discoveries_repository import DiscoveriesRepositoryInterface
from simod_http.discoveries_repository_mongo import MongoDiscoveriesRepository


def inject_broker_client(api: FastAPI, client: BrokerClient) -> FastAPI:
    api.state.app._broker_client = client
    return api


def stub_broker_client() -> BrokerClient:
    channel = MagicMock()
    connection = MagicMock(spec=BlockingConnection)
    connection.channel.return_value = channel
    client = BrokerClient("", "", "", connection=connection)
    client.basic_publish_discovery = MagicMock()
    client.publish_discovery = MagicMock()
    client.connect = MagicMock()
    return client


def inject_discoveries_repository(api: FastAPI, repository: DiscoveriesRepositoryInterface) -> FastAPI:
    api.state.app._discoveries_repository = repository
    return api


def stub_discoveries_repository_failing() -> MongoDiscoveriesRepository:
    repository = MongoDiscoveriesRepository(mongo_client=MagicMock(), database="simod", collection="discoveries")
    repository.get = MagicMock(side_effect=NotFound(message="Discovery not found", discovery_id="123"))
    repository.save = MagicMock()
    return repository


def path_to_current_file_dir() -> Path:
    return Path(__file__).parent


class TestAPI:
    def test_root(self):
        client = self.make_failing_client()

        response = client.get("/")

        assert response.status_code == 404
        assert response.json() == {
            "error": "Not Found",
        }

    def test_catch_all_route(self):
        client = self.make_failing_client()

        response = client.get("/foo")

        assert response.status_code == 404
        assert response.json() == {
            "error": "Not Found",
        }

    def test_discoveries_get(self):
        client = self.make_failing_client()

        response = client.get("/discoveries/123")

        assert response.status_code == 404
        assert response.json() == {
            "discovery_id": "123",
            "error": "Discovery not found",
        }

    def test_discoveries_patch(self):
        client = self.make_failing_client()

        response = client.patch("/discoveries/123")

        assert response.status_code == 422
        assert response.json() == {
            "error": [
                {
                    "loc": ["body"],
                    "msg": "field required",
                    "type": "value_error.missing",
                }
            ]
        }

    def test_discoveries_post(self):
        client = self.make_client()

        response = self.post_discovery(client)

        assert response.status_code == 202
        assert "discovery_id" in response.json()

    def test_discoveries_file(self):
        client = self.make_client()
        request_id = "123"

        archive_file = f"{request_id}.tar.gz"
        response = client.get(f"/discoveries/{request_id}/{archive_file}")

        assert response.status_code == 404
        assert response.json() == {
            "error": f"File not found: {archive_file}",
            "discovery_id": request_id,
            "discovery_status": "pending",
        }

    def test_discoveries_status_patch(self):
        client = self.make_client(status=DiscoveryStatus.RUNNING)
        request_id = "123"

        response = client.patch(f"/discoveries/{request_id}", json={"status": DiscoveryStatus.RUNNING})

        assert response.status_code == 200
        assert response.json() == {
            "discovery_id": request_id,
            "discovery_status": DiscoveryStatus.RUNNING.value,
        }

    def test_discoveries_delete(self):
        client = self.make_client()
        request_id = "123"

        response = client.delete(f"/discoveries/{request_id}")

        assert response.status_code == 200
        assert response.json() == {
            "discovery_id": request_id,
            "discovery_status": DiscoveryStatus.DELETED.value,
        }

    @staticmethod
    def make_failing_client() -> TestClient:
        inject_discoveries_repository(api, stub_discoveries_repository_failing())
        inject_broker_client(api, stub_broker_client())
        return TestClient(api)

    @staticmethod
    def make_client(status: Optional[DiscoveryStatus] = DiscoveryStatus.PENDING) -> TestClient:
        repository = MongoDiscoveriesRepository(mongo_client=MagicMock(), database="simod", collection="requests")
        repository.get = MagicMock(
            return_value=Discovery(
                _id="123",
                status=status,
                configuration_path="configuration.yaml",
                output_dir="output",
            )
        )
        repository.save = MagicMock()
        repository.save_status = MagicMock()
        inject_discoveries_repository(api, repository)

        inject_broker_client(api, stub_broker_client())

        return TestClient(api)

    @staticmethod
    def post_discovery(client: TestClient) -> Response:
        assets_dir = path_to_current_file_dir() / "assets"
        configuration_path = assets_dir / "sample.yaml"
        event_log_path = assets_dir / "PurchasingExample.xes"

        data = MultipartEncoder(
            fields={
                "configuration": ("configuration.yaml", configuration_path.open("rb"), "text/yaml"),
                "event_log": ("event_log.xes", event_log_path.open("rb"), "application/xml"),
            }
        )

        response = client.post(
            "/discoveries",
            headers={"Content-Type": data.content_type},
            content=data.to_string(),
        )

        return response
