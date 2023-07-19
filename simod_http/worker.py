import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from celery import Celery

from simod_http.discoveries.model import Discovery, DiscoveryStatus
from simod_http.discoveries.repository import DiscoveriesRepositoryInterface
from simod_http.discoveries.repository_mongo import make_mongo_client, make_mongo_discoveries_repository

app = Celery("simod_http_worker")

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    enable_utc=True,
    timezone="Europe/Tallinn",
    result_expires=60 * 60 * 24 * 7,
)


@app.task(name="simod_http.worker.run_discovery", bind=True)
def run_discovery(self, configuration_path: str, output_dir: str) -> dict:
    repository = make_discoveries_repository()

    discovery = repository.get(self.request.id)
    discovery.started_timestamp = datetime.now()
    discovery.status = DiscoveryStatus.RUNNING
    repository.save(discovery)

    result = start_discovery_subprocess(configuration_path, output_dir)
    result.id = self.request.id
    return result.__dict__


@app.task(name="simod_http.worker.post_process_discovery_result")
def post_process_discovery_result(discovery_result: dict) -> str:
    from simod_http.main import api

    result = DiscoveryResult(**discovery_result)

    repository = make_discoveries_repository()
    discovery = repository.get(result.id)

    if result.return_code != 0:
        discovery.status = DiscoveryStatus.FAILED
        repository.save(discovery)
        return

    discovery.status = DiscoveryStatus.SUCCEEDED
    discovery.finished_timestamp = datetime.now()

    try:
        archive_path = archive_discovery_results(discovery)
        archive_name = Path(archive_path).name
        discovery.archive_url = api.url_path_for(
            "get_discovery_file", discovery_id=discovery.id, file_name=archive_name
        )
    except Exception as e:
        discovery.status = DiscoveryStatus.FAILED
        raise e
    finally:
        repository.save(discovery)

    # TODO: call callback if available

    return archive_path


def make_discoveries_repository() -> DiscoveriesRepositoryInterface:
    mongo_client = make_mongo_client()
    return make_mongo_discoveries_repository(mongo_client)


@dataclass
class DiscoveryResult:
    return_code: int
    id: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None


def start_discovery_subprocess(configuration_path: str, output_dir: str) -> DiscoveryResult:
    result = subprocess.run(
        ["bash", "/usr/src/Simod/run.sh", configuration_path, output_dir],
        cwd="/usr/src/Simod/",
        capture_output=True,
        check=True,
    )
    return DiscoveryResult(return_code=result.returncode, stdout=result.stdout, stderr=result.stderr)


def archive_discovery_results(discovery: Discovery) -> str:
    results_dir = os.path.join(discovery.output_dir, "best_result")
    archive_path = os.path.join(discovery.output_dir, "results")  # name without suffix
    archive_path = shutil.make_archive(archive_path, format="gztar", root_dir=results_dir)
    shutil.rmtree(results_dir)
    return archive_path
