from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from httpx import Response
from requests_toolbelt import MultipartEncoder
from starlette.testclient import TestClient

from simod_http.app import make_simod_app
from simod_http.discoveries.model import Discovery, DiscoveryStatus
from simod_http.discoveries.repository_mongo import DiscoveriesRepositoryInterface, MongoDiscoveriesRepository
from simod_http.exceptions import NotFound
from simod_http.main import make_fastapi_app
from simod_http.routes.discoveries import DeleteDiscoveriesResponse

api = make_fastapi_app()
api.state.app = make_simod_app()


def inject_discoveries_repository(api: FastAPI, repository: DiscoveriesRepositoryInterface) -> FastAPI:
    api.state.app._discoveries_repository = repository
    return api


def stub_discoveries_repository_failing() -> MongoDiscoveriesRepository:
    repository = MongoDiscoveriesRepository(mongo_client=MagicMock(), database="simod", collection="discoveries")
    repository.get = MagicMock(side_effect=NotFound(message="Discovery not found", discovery_id="123"))
    repository.save = MagicMock()
    repository.delete = MagicMock(side_effect=DeleteDiscoveriesResponse(deleted_amount=1))
    return repository


def path_to_current_file_dir() -> Path:
    return Path(__file__).parent


class TestAPI:
    def test_root(self):
        client = self.make_failing_client()

        response = client.get("/")

        assert response.status_code == 404
        assert response.json() == {"error": {"message": "Not Found"}}

    def test_catch_all_route(self):
        client = self.make_failing_client()

        response = client.get("/foo")

        assert response.status_code == 404
        assert response.json() == {"error": {"message": "Not Found"}}

    def test_discoveries_get(self):
        client = self.make_failing_client()

        response = client.get("/discoveries/123")

        assert response.status_code == 404
        assert response.json() == {"error": {"discovery_id": "123", "message": "Discovery not found"}}

    def test_discoveries_patch(self):
        client = self.make_failing_client()

        response = client.patch("/discoveries/123")

        assert response.status_code == 401

    def test_discoveries_post(self):
        client = self.make_client()

        with patch("fastapi.BackgroundTasks.add_task"):
            response = self.post_discovery(client)

        assert response.status_code == 202
        assert "_id" in response.json()

    def test_discoveries_file(self):
        client = self.make_client()
        request_id = "123"

        archive_file = f"{request_id}.tar.gz"
        response = client.get(f"/discoveries/{request_id}/{archive_file}")

        assert response.status_code == 404
        assert response.json() == {
            "error": {
                "message": f"File not found: {archive_file}",
                "discovery_id": request_id,
                "discovery_status": "pending",
            }
        }

    def test_discoveries_status_patch(self):
        client = self.make_client(status=DiscoveryStatus.RUNNING)
        request_id = "123"

        response = client.patch(f"/discoveries/{request_id}", json={"status": DiscoveryStatus.RUNNING})

        assert response.status_code == 401

    def test_discoveries_delete(self):
        client = self.make_client()
        request_id = "123"

        response = client.delete(f"/discoveries/{request_id}")

        assert response.status_code == 401

    @staticmethod
    def make_failing_client() -> TestClient:
        inject_discoveries_repository(api, stub_discoveries_repository_failing())
        return TestClient(api)

    @staticmethod
    def make_client(status: Optional[DiscoveryStatus] = DiscoveryStatus.PENDING) -> TestClient:
        repository = MongoDiscoveriesRepository(mongo_client=MagicMock(), database="simod", collection="discoveries")
        repository.get = MagicMock(
            return_value=Discovery(
                _id="123",
                status=status,
                configuration_path="configuration.yaml",
                output_dir="output",
            )
        )
        repository.create = MagicMock(
            return_value=Discovery(_id="123", status=status, configuration_path="configuration.yaml")
        )
        repository.save = MagicMock()
        repository.save_status = MagicMock()
        repository.delete_all = MagicMock(return_value=1)
        inject_discoveries_repository(api, repository)

        return TestClient(api)

    @staticmethod
    def post_discovery(client: TestClient) -> Response:
        assets_dir = path_to_current_file_dir() / "assets"
        configuration_path = assets_dir / "sample.yaml"
        event_log_path = assets_dir / "AcademicCredentials_train.csv"

        data = MultipartEncoder(
            fields={
                "configuration": ("configuration.yaml", configuration_path.open("rb"), "text/yaml"),
                "event_log": ("event_log.csv", event_log_path.open("rb"), "text/csv"),
            }
        )

        response = client.post(
            "/discoveries/",
            headers={"Content-Type": data.content_type},
            content=data.to_string(),
        )

        return response
