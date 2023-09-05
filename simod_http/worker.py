import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from celery import Celery

from simod_http.discoveries.model import Discovery, DiscoveryStatus, NotificationMethod, NotificationSettings
from simod_http.discoveries.repository import DiscoveriesRepositoryInterface
from simod_http.discoveries.repository_mongo import make_mongo_client, make_mongo_discoveries_repository
from simod_http.exceptions import NotSupported

CELERY_EXPIRATION_TIMEDELTA = 60 * 60 * 24 * 7  # seconds

app = Celery("simod_http_worker")

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    enable_utc=True,
    timezone="Europe/Tallinn",
    result_expires=CELERY_EXPIRATION_TIMEDELTA,
)


@app.task(name="simod_http.worker.get_schema_json", bind=True)
def get_schema_json(self) -> str:
    result = subprocess.run(
        ["poetry", "run", "simod", "--schema-json"],
        cwd="/usr/src/Simod/",
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8")


@app.task(name="simod_http.worker.get_schema_yaml", bind=True)
def get_schema_yaml(self) -> str:
    result = subprocess.run(
        ["poetry", "run", "simod", "--schema-yaml"],
        cwd="/usr/src/Simod/",
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8")


@app.task(name="simod_http.worker.run_discovery", bind=True)
def run_discovery(self, configuration_path: str, output_dir: str) -> dict:
    repository = _make_discoveries_repository()

    discovery = repository.get(self.request.id)
    discovery.started_timestamp = datetime.now()
    discovery.status = DiscoveryStatus.RUNNING
    repository.save(discovery)

    result = _start_discovery_subprocess(configuration_path, output_dir)  # TODO: if fails, update status
    result.id = self.request.id
    return result.__dict__


@app.task(name="simod_http.worker.post_process_discovery_result")
def post_process_discovery_result(discovery_result: dict) -> str:
    from simod_http.main import api

    result = DiscoveryResult(**discovery_result)

    repository = _make_discoveries_repository()
    discovery = repository.get(result.id)

    if result.return_code != 0:
        discovery.status = DiscoveryStatus.FAILED
        repository.save(discovery)
        return ""

    discovery.status = DiscoveryStatus.SUCCEEDED
    discovery.finished_timestamp = datetime.now()

    try:
        archive_path = _archive_discovery_results(discovery)
        archive_name = Path(archive_path).name
        archive_url = api.url_path_for("get_discovery_file", discovery_id=discovery.id, file_name=archive_name)
        discovery.archive_url = f"/{api.root_path.strip('/')}/{archive_url.strip('/')}"
        api.state.app.logger.info(
            f"Discovery {discovery.id}: archive URL: {discovery.archive_url}, root path: {api.root_path}"
        )
    except Exception as e:
        discovery.status = DiscoveryStatus.FAILED
        raise e
    finally:
        repository.save(discovery)

    try:
        _resolve_notification(discovery.notification_settings, discovery.archive_url)
        discovery.notified = True
        repository.save(discovery)
    except Exception as e:
        api.state.app.logger.error(
            f"Failed to resolve notification with settings: {discovery.notification_settings}. Exception: {e}"
        )

    return archive_path


@app.task(name="simod_http.worker.mark_expired_discoveries")
def mark_expired_discoveries() -> list[str]:
    from simod_http.main import api

    expiration_delta: int = api.state.app.configuration.storage.discovery_expiration_timedelta

    repository = _make_discoveries_repository()
    discoveries_ids = []

    for discovery in repository.get_all():
        if discovery.finished_timestamp is None:
            continue

        has_expired = discovery.finished_timestamp.timestamp() + expiration_delta < datetime.now().timestamp()
        discovery_already_processed = discovery.status in [
            DiscoveryStatus.EXPIRED,
            DiscoveryStatus.DELETED,
        ]
        if has_expired and not discovery_already_processed:
            api.state.app.logger.info(f"Marking discovery {discovery.id} as expired")
            discovery.status = DiscoveryStatus.EXPIRED
            repository.save(discovery)
            discoveries_ids.append(discovery.id)

    return discoveries_ids


@app.task(name="simod_http.worker.clean_expired_discovery_results")
def clean_expired_discovery_results() -> list:
    from simod_http.main import api

    repository = _make_discoveries_repository()
    discoveries = repository.get_all()
    discoveries_ids = []

    for discovery in discoveries:
        if discovery.status != DiscoveryStatus.EXPIRED:
            continue

        try:
            _remove_fs_directories(discovery)
        except Exception as e:
            api.state.app.logger.error(f"Failed to remove directories of discovery {discovery.id}: {e}")
            continue

        discovery.status = DiscoveryStatus.DELETED
        repository.save(discovery)
        discoveries_ids.append(discovery.id)

    return discoveries_ids


def _make_discoveries_repository() -> DiscoveriesRepositoryInterface:
    mongo_client = make_mongo_client()
    return make_mongo_discoveries_repository(mongo_client)


def _remove_fs_directories(discovery: Discovery):
    if not discovery.output_dir:
        return

    if not os.path.exists(discovery.output_dir):
        return

    shutil.rmtree(discovery.output_dir)


@dataclass
class DiscoveryResult:
    return_code: int
    id: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None


def _start_discovery_subprocess(configuration_path: str, output_dir: str) -> DiscoveryResult:
    result = subprocess.run(
        ["bash", "/usr/src/Simod/run.sh", configuration_path, output_dir],
        cwd="/usr/src/Simod/",
        capture_output=True,
        check=True,
    )
    return DiscoveryResult(return_code=result.returncode, stdout=result.stdout, stderr=result.stderr)


def _archive_discovery_results(discovery: Discovery) -> str:
    results_dir = os.path.join(discovery.output_dir, "best_result")
    archive_path = os.path.join(discovery.output_dir, "results")  # name without suffix
    archive_path = shutil.make_archive(archive_path, format="gztar", root_dir=results_dir)
    shutil.rmtree(results_dir)
    return archive_path


def _resolve_notification(notification_settings: Optional[NotificationSettings], archive_url: str):
    if not notification_settings:
        return

    if notification_settings.method == NotificationMethod.HTTP:
        _notify_http(notification_settings.callback_url, archive_url)
    elif notification_settings.method == NotificationMethod.EMAIL:
        raise NotSupported("Email notification is not supported yet.")
    else:
        raise NotSupported(f"Notification method {notification_settings.method} is not supported.")


def _notify_http(callback_url: str, archive_url: str):
    requests.post(callback_url, json={"archive_url": archive_url})
