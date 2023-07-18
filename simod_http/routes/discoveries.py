import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Union, Optional, List

from fastapi import APIRouter, UploadFile, BackgroundTasks, Request, FastAPI
from starlette import status

from simod_http.app import Application
from simod_http.discoveries.model import (
    Discovery,
    DiscoveryStatus,
    NotificationMethod,
    NotificationSettings,
)
from simod_http.exceptions import UnsupportedMediaType, InternalServerError, NotSupported

router = APIRouter(prefix="/discoveries")


@router.get("/", response_model=List[Discovery])
async def get_discoveries(request: Request) -> List[Discovery]:
    """
    Get all business process simulation model discoveries.
    """
    app = request.app.state.app

    discoveries = app.discoveries_repository.get_all()

    return discoveries


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def create_discovery(
    request: Request,
    background_tasks: BackgroundTasks,
    configuration: UploadFile,
    event_log: UploadFile,
    callback_url: Optional[str] = None,
    email: Optional[str] = None,
) -> Discovery:
    """
    Create a new business process simulation model discovery discovery.
    """
    app = request.app.state.app

    if email is not None:
        raise NotSupported(message="Email notifications are not supported")

    notification_settings = _notification_settings_from_params(callback_url, email)
    event_log_path = _save_uploaded_event_log(event_log, app)
    configuration_path = _update_and_save_configuration(configuration, event_log_path, app)

    discovery = Discovery(
        notification_settings=notification_settings,
        configuration_path=str(configuration_path),
        status=DiscoveryStatus.ACCEPTED,
    )

    discovery = app.discoveries_repository.create(discovery, app.configuration.storage.discoveries_path)
    app.logger.info(f"New discovery {discovery.id}: status={discovery.status}")

    background_tasks.add_task(_process_new_discovery, discovery, app, request.app)

    return discovery


@dataclass
class DeleteDiscoveriesResponse:
    deleted_amount: int


@router.delete("/")
async def delete_discoveries(request: Request) -> DeleteDiscoveriesResponse:
    """
    Delete all business process simulation model discoveries.
    """
    app = request.app.state.app

    discoveries = app.discoveries_repository.get_all()

    try:
        _remove_fs_directories(discoveries)
    except Exception as e:
        raise InternalServerError(discovery_id=None, message=f"Failed to remove directories of discoveries: {e}")

    deleted_amount = app.discoveries_repository.delete_all()

    return DeleteDiscoveriesResponse(deleted_amount=deleted_amount)


def _notification_settings_from_params(
    callback_url: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[NotificationSettings]:
    if callback_url is not None:
        notification_settings = NotificationSettings(
            method=NotificationMethod.HTTP,
            callback_url=callback_url,
        )
    elif email is not None:
        notification_settings = NotificationSettings(
            method=NotificationMethod.EMAIL,
            email=email,
        )
    else:
        notification_settings = None

    return notification_settings


def _save_uploaded_event_log(upload: UploadFile, app: Application) -> Path:
    # TODO: don't accept anything but CSV
    event_log_file_extension = _infer_event_log_file_extension_from_header(upload.content_type)
    if event_log_file_extension is None:
        raise UnsupportedMediaType(message="Unsupported event log file type")

    content = upload.file.read()
    upload.file.close()

    event_log_file = app.files_repository.create(content, event_log_file_extension)
    event_log_file_path = app.files_repository.file_path(event_log_file.file_name)
    app.logger.info(f"Uploaded event log file: {event_log_file_path}")

    return app.files_repository.file_path(event_log_file.file_name)


def _infer_event_log_file_extension_from_header(content_type: str) -> Union[str, None]:
    if "text/csv" in content_type:
        return ".csv"
    elif "application/xml" in content_type or "text/xml" in content_type:
        return ".xes"
    else:
        return None


def _update_and_save_configuration(upload: UploadFile, event_log_path: Path, app: Application):
    content = upload.file.read()
    upload.file.close()

    regexp = r"train_log_path: .*\n"
    replacement = f"train_log_path: {event_log_path.absolute()}\n"
    content = re.sub(regexp, replacement, content.decode("utf-8"))

    # test log is not supported in discovery params
    regexp = r"test_log_path: .*\n"
    replacement = "test_log_path: null\n"
    content = re.sub(regexp, replacement, content)

    new_file = app.files_repository.create(content.encode("utf-8"), ".yaml")
    new_file_path = app.files_repository.file_path(new_file.file_name)
    app.logger.info(f"Uploaded configuration file: {new_file_path}")

    return new_file_path


def _process_new_discovery(discovery: Discovery, app: Application, fastapi_app: FastAPI):
    app.logger.info(
        f"Processing discovery {discovery.id}: "
        f"status={discovery.status}, "
        f"configuration_path={discovery.configuration_path}"
    )

    try:
        _pre_start_discovery(app, discovery)
        _start_discovery(discovery)
    except Exception as e:
        discovery.status = DiscoveryStatus.FAILED
        app.logger.error(e)
    finally:
        _post_start_discovery(app, discovery, fastapi_app)

    app.logger.info(f"Processed discovery {discovery.id}, {discovery.status}")


def _pre_start_discovery(app: Application, discovery: Discovery):
    discovery.output_dir = f"{app.configuration.storage.discoveries_path}/{discovery.id}"
    discovery.status = DiscoveryStatus.PENDING
    app.discoveries_repository.save(discovery)


def _start_discovery(discovery: Discovery):
    try:
        discovery.started_timestamp = datetime.now()
        process = _start_discovery_subprocess(discovery.configuration_path, discovery.output_dir)
    except subprocess.CalledProcessError as e:
        raise Exception(f"Discovery {discovery.id} failed: {e}, stdout={e.stdout}, stderr={e.stderr}")
    discovery.status = DiscoveryStatus.SUCCEEDED if process.returncode == 0 else DiscoveryStatus.FAILED


def _start_discovery_subprocess(configuration_path: str, output_dir: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "/usr/src/Simod/run.sh", configuration_path, output_dir],
        cwd="/usr/src/Simod/",
        capture_output=True,
        check=True,
    )


def _post_start_discovery(app: Application, discovery: Discovery, fastapi_app: FastAPI):
    discovery.finished_timestamp = datetime.now()

    archive_path = _archive_discovery_results(discovery)
    archive_name = Path(archive_path).name
    discovery.archive_url = fastapi_app.url_path_for(
        "get_discovery_file", discovery_id=discovery.id, file_name=archive_name
    )

    # TODO: call callback if available

    app.discoveries_repository.save(discovery)


def _archive_discovery_results(discovery: Discovery) -> str:
    results_dir = os.path.join(discovery.output_dir, "best_result")
    archive_path = os.path.join(discovery.output_dir, "results")  # name without suffix
    archive_path = shutil.make_archive(archive_path, format="gztar", root_dir=results_dir)
    shutil.rmtree(results_dir)
    return archive_path


def _remove_fs_directories(discoveries: List[Discovery]):
    for discovery in discoveries:
        if discovery.output_dir:
            output_dir = Path(discovery.output_dir)
            if output_dir.exists():
                shutil.rmtree(output_dir)
