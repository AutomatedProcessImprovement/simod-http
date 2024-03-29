import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, List, Optional, Union

from celery.result import AsyncResult
from fastapi import APIRouter, BackgroundTasks, Depends, Request, UploadFile
from starlette import status

from simod_http.app import Application
from simod_http.auth import get_current_user
from simod_http.discoveries.model import (
    Discovery,
    DiscoveryStatus,
    NotificationMethod,
    NotificationSettings,
)
from simod_http.exceptions import InternalServerError, UnsupportedMediaType
from simod_http.worker import post_process_discovery_result, run_discovery

router = APIRouter(prefix="/discoveries")


@router.get("/", response_model=List[Discovery])
async def get_discoveries(
    request: Request,
    current_user: Annotated[Union[str, None], Depends(get_current_user)],
) -> List[Discovery]:
    """
    Get all business process simulation model discoveries.
    """
    app = request.app.state.app

    app.logger.info(f"User {current_user} is getting all discoveries")

    discoveries = app.discoveries_repository.get_all()

    return discoveries


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def create_discovery(
    request: Request,
    background_tasks: BackgroundTasks,
    event_log: UploadFile,
    configuration: Union[UploadFile, None] = None,
    callback_url: Optional[str] = None,
) -> Discovery:
    """
    Create a new business process simulation model discovery discovery.
    """
    app = request.app.state.app

    if not _is_valid_event_log_format(event_log):
        raise UnsupportedMediaType(
            message=f"Unsupported event log file type: {event_log.content_type} for {event_log.filename}"
        )

    if not _is_valid_event_log_size(event_log):
        raise UnsupportedMediaType(message=f"Unsupported event log file size: {event_log.size}")

    notification_settings = _notification_settings_from_params(callback_url, None)
    event_log_path = _save_uploaded_event_log(event_log, app)
    configuration_path = _update_and_save_configuration(configuration, event_log_path, app)

    discovery = Discovery(
        notification_settings=notification_settings,
        configuration_path=str(configuration_path),
        status=DiscoveryStatus.ACCEPTED,
    )

    discovery = app.discoveries_repository.create(discovery, app.configuration.storage.discoveries_path)
    app.logger.info(f"New discovery {discovery.id}: status={discovery.status}")

    background_tasks.add_task(_process_new_discovery, discovery, app)

    return discovery


@dataclass
class DeleteDiscoveriesResponse:
    deleted_amount: int


@router.delete("/")
async def delete_discoveries(
    request: Request,
    current_user: Annotated[Union[str, None], Depends(get_current_user)],
) -> DeleteDiscoveriesResponse:
    """
    Delete all business process simulation model discoveries.
    """
    app = request.app.state.app

    app.logger.info(f"User {current_user} is deleting all discoveries")

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


def _is_valid_event_log_format(upload: UploadFile) -> bool:
    if upload.content_type == "text/csv":
        return True

    if upload.content_type == "application/octet-stream":
        return upload.filename.endswith(".csv") or _is_file_compressed(upload)

    return False


def _is_file_compressed(file: UploadFile) -> bool:
    # supported compression by pandas.read_csv: '.gz', '.bz2', '.zip', '.xz', '.zst', '.tar', '.tar.gz', '.tar.xz' or '.tar.bz2'
    return (
        file.filename.endswith(".gz")
        or file.filename.endswith(".bz2")
        or file.filename.endswith(".zip")
        or file.filename.endswith(".xz")
        or file.filename.endswith(".zst")
        or file.filename.endswith(".tar")
        or file.filename.endswith(".tar.gz")
        or file.filename.endswith(".tar.xz")
        or file.filename.endswith(".tar.bz2")
    )


def _is_valid_event_log_size(
    upload: UploadFile, raw_size_limit: int = 500e6, compressed_size_limit: int = 70e6
) -> bool:
    # Accept any file if upload.size is not available
    if upload.size is None or upload.size <= 0:
        return True

    if _is_file_compressed(upload):
        return upload.size <= compressed_size_limit

    return upload.size <= raw_size_limit


def _save_uploaded_event_log(upload: UploadFile, app: Application) -> Path:
    file_extension = "".join(Path(upload.filename).suffixes)
    content = upload.file.read()
    upload.file.close()

    log_file = app.files_repository.create(content, file_extension)
    log_path = app.files_repository.file_path(log_file.file_name)
    app.logger.info(f"Uploaded event log file: {log_path}")

    return app.files_repository.file_path(log_path)


def _update_and_save_configuration(upload: Optional[UploadFile], event_log_path: Path, app: Application):
    if upload is None:
        content = Path(app.configuration.default_configuration_path).read_bytes()
    else:
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


def _process_new_discovery(discovery: Discovery, app: Application):
    app.logger.info(
        f"Processing discovery {discovery.id}: "
        f"status={discovery.status}, "
        f"configuration_path={discovery.configuration_path}"
    )

    try:
        _pre_start_discovery(app, discovery)
        result = _start_discovery(app, discovery)
        result.forget()
    except Exception as e:
        discovery.status = DiscoveryStatus.FAILED
        discovery.finished_timestamp = datetime.now()
        app.discoveries_repository.save(discovery)
        app.logger.error(e)


def _pre_start_discovery(app: Application, discovery: Discovery):
    discovery.output_dir = f"{app.configuration.storage.discoveries_path}/{discovery.id}"
    discovery.status = DiscoveryStatus.PENDING
    app.discoveries_repository.save(discovery)


def _start_discovery(app: Application, discovery: Discovery) -> AsyncResult:
    return run_discovery.apply_async(
        args=[discovery.configuration_path, discovery.output_dir],
        task_id=discovery.id,
        link=post_process_discovery_result.s(),
    )


def _remove_fs_directories(discoveries: List[Discovery]):
    for discovery in discoveries:
        if discovery.output_dir:
            output_dir = Path(discovery.output_dir)
            if output_dir.exists():
                shutil.rmtree(output_dir)
