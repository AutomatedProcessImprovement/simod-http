import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Union, Optional, List

from fastapi import Response, Form, APIRouter
from starlette import status
from starlette.background import BackgroundTasks
from starlette.datastructures import UploadFile
from starlette.requests import Request
from starlette.responses import FileResponse

from simod_http.app import Application
from simod_http.configurations import HttpConfiguration
from simod_http.discoveries import Discovery, DiscoveryStatus, NotificationMethod, NotificationSettings
from simod_http.exceptions import NotFound, UnsupportedMediaType, InternalServerError, NotSupported

router = APIRouter(prefix="/discoveries")


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def create_discovery(
    request: Request,
    background_tasks: BackgroundTasks,
    configuration=Form(),
    event_log=Form(),
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
        output_dir=None,
    )

    discovery = app.discoveries_repository.create(discovery, app.configuration.storage.discoveries_path)
    app.logger.info(f"New discovery {discovery.get_id()}: status={discovery.status}")

    background_tasks.add_task(_process_post_discovery, discovery, app)

    return discovery


@router.get("/")
async def read_discoveries(request: Request) -> List[Discovery]:
    """
    Get all business process simulation model discoveries.
    """
    app = request.app.state.app

    discoveries = app.discoveries_repository.get_all()

    return discoveries


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


# Routes: /{discovery_id}


@router.get("/{discovery_id}/configuration")
async def read_discovery_configuration(request: Request, discovery_id: str) -> FileResponse:
    """
    Get the configuration of the discovery.
    """
    app = request.app.state.app

    discovery = await get_discovery(app, discovery_id)

    if not discovery.configuration_path:
        raise InternalServerError(
            discovery_id=discovery_id,
            discovery_status=discovery.status,
            message=f"Discovery {discovery_id} has no configuration file",
        )

    file_path = Path(discovery.configuration_path)
    if not file_path.exists():
        raise NotFound(
            discovery_id=discovery_id,
            discovery_status=discovery.status,
            message=f"File not found: {file_path}",
        )

    media_type = _infer_media_type_from_extension(file_path.name)

    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_path.name}"',
        },
    )


@router.get("/{discovery_id}/{file_name}")
async def read_discovery_file(request: Request, discovery_id: str, file_name: str) -> Response:
    """
    Get a file for the discovery.
    """
    app = request.app.state.app

    discovery = await get_discovery(app, discovery_id)

    if not discovery.output_dir:
        raise InternalServerError(
            discovery_id=discovery_id,
            discovery_status=discovery.status,
            message=f"Discovery {discovery_id} has no output directory",
        )

    file_path = Path(discovery.output_dir) / file_name
    if not file_path.exists():
        raise NotFound(
            discovery_id=discovery_id,
            discovery_status=discovery.status,
            message=f"File not found: {file_name}",
        )

    media_type = _infer_media_type_from_extension(file_name)

    return Response(
        content=file_path.read_bytes(),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_name}"',
        },
    )


@router.get("/{discovery_id}")
async def read_discovery(request: Request, discovery_id: str) -> Discovery:
    """
    Get the status of the discovery.
    """
    app = request.app.state.app

    return await get_discovery(app, discovery_id)


@dataclass
class PatchDiscoveryPayload:
    status: DiscoveryStatus


# TODO: status should updated automatically by the background task
@router.patch("/{discovery_id}")
async def patch_discovery(request: Request, discovery_id: str, payload: PatchDiscoveryPayload) -> Discovery:
    """
    Update the status of the discovery.
    """
    app = request.app.state.app

    try:
        archive_url = None
        if payload.status == DiscoveryStatus.SUCCEEDED:
            archive_url = make_results_url_for(discovery_id, payload.status, app.configuration.http)

        app.discoveries_repository.save_status(discovery_id, payload.status, archive_url)
    except Exception as e:
        raise InternalServerError(
            discovery_id=discovery_id,
            message=f"Failed to update discovery {discovery_id}: {e}",
        )

    return await get_discovery(app, discovery_id)


@dataclass
class DeleteDiscoveryResponse:
    id: str
    status: DiscoveryStatus = DiscoveryStatus.DELETED


@router.delete("/{discovery_id}")
async def delete_discovery(request: Request, discovery_id: str) -> DeleteDiscoveryResponse:
    app = request.app.state.app

    discovery = await get_discovery(app, discovery_id)

    discovery.status = DiscoveryStatus.DELETED
    app.discoveries_repository.save_status(discovery_id, discovery.status)

    return DeleteDiscoveryResponse(id=discovery_id, status=discovery.status)


# Controller helpers


async def get_discovery(app: Application, discovery_id: str) -> Discovery:
    try:
        discovery = app.discoveries_repository.get(discovery_id)
        if discovery is None:
            raise NotFound(message="Discovery not found", discovery_id=discovery_id)
    except NotFound as e:
        raise e
    except Exception as e:
        raise InternalServerError(
            discovery_id=discovery_id,
            message=f"Failed to load discovery {discovery_id}: {e}",
        )
    return discovery


def _infer_media_type_from_extension(file_name) -> str:
    if file_name.endswith(".csv"):
        media_type = "text/csv"
    elif file_name.endswith(".xml"):
        media_type = "application/xml"
    elif file_name.endswith(".xes"):
        media_type = "application/xml"
    elif file_name.endswith(".bpmn"):
        media_type = "application/xml"
    elif file_name.endswith(".json"):
        media_type = "application/json"
    elif file_name.endswith(".yaml") or file_name.endswith(".yml"):
        media_type = "text/yaml"
    elif file_name.endswith(".png"):
        media_type = "image/png"
    elif file_name.endswith(".jpg") or file_name.endswith(".jpeg"):
        media_type = "image/jpeg"
    elif file_name.endswith(".pdf"):
        media_type = "application/pdf"
    elif file_name.endswith(".txt"):
        media_type = "text/plain"
    elif file_name.endswith(".zip"):
        media_type = "application/zip"
    elif file_name.endswith(".gz"):
        media_type = "application/gzip"
    elif file_name.endswith(".tar"):
        media_type = "application/tar"
    elif file_name.endswith(".tar.gz"):
        media_type = "application/tar+gzip"
    elif file_name.endswith(".tar.bz2"):
        media_type = "application/x-bzip2"
    else:
        media_type = "application/octet-stream"

    return media_type


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
    event_log_file_extension = _infer_event_log_file_extension_from_header(upload.content_type)
    if event_log_file_extension is None:
        raise UnsupportedMediaType(message="Unsupported event log file type")

    content = upload.file.read()
    upload.file.close()

    event_log_file = app.files_repository.create(content, event_log_file_extension)
    event_log_file_path = app.files_repository.file_path(event_log_file.file_name)
    app.logger.info(f"Uploaded event log file: {event_log_file_path}")

    return app.files_repository.file_path(event_log_file.file_name)


def _update_and_save_configuration(upload: UploadFile, event_log_path: Path, app: Application):
    content = upload.file.read()
    upload.file.close()

    regexp = r"log_path: .*\n"
    replacement = f"log_path: {event_log_path.absolute()}\n"
    content = re.sub(regexp, replacement, content.decode("utf-8"))

    # test log is not supported in discovery params
    regexp = r"test_log_path: .*\n"
    replacement = "test_log_path: None\n"
    content = re.sub(regexp, replacement, content)

    new_file = app.files_repository.create(content.encode("utf-8"), ".yaml")
    new_file_path = app.files_repository.file_path(new_file.file_name)
    app.logger.info(f"Uploaded configuration file: {new_file_path}")

    return new_file_path


def _process_post_discovery(discovery: Discovery, app: Application):
    app.logger.info(
        f"Processing discovery {discovery.get_id()}: "
        f"status={discovery.status}, "
        f"configuration_path={discovery.configuration_path}"
    )

    try:
        app.broker_client.publish_discovery(discovery)
        discovery.status = DiscoveryStatus.PENDING
        app.discoveries_repository.save(discovery)
    except Exception as e:
        discovery.status = DiscoveryStatus.FAILED
        app.discoveries_repository.save(discovery)
        app.logger.error(e)
        raise e

    app.logger.info(f"Processed discovery {discovery.get_id()}, {discovery.status}")


def _save_event_log(event_log: UploadFile, discovery: Discovery):
    event_log_file_extension = _infer_event_log_file_extension_from_header(event_log.content_type)
    if event_log_file_extension is None:
        raise UnsupportedMediaType(message="Unsupported event log file type")

    event_log_path = Path(discovery.output_dir) / f"event_log{event_log_file_extension}"
    event_log_path.write_bytes(event_log.file.read())

    return event_log_path


def _infer_event_log_file_extension_from_header(content_type: str) -> Union[str, None]:
    if "text/csv" in content_type:
        return ".csv"
    elif "application/xml" in content_type or "text/xml" in content_type:
        return ".xml"
    else:
        return None


def _remove_fs_directories(discoveries: List[Discovery]):
    for discovery in discoveries:
        if discovery.output_dir:
            output_dir = Path(discovery.output_dir)
            if output_dir.exists():
                shutil.rmtree(output_dir)


def make_results_url_for(discovery_id: str, status: DiscoveryStatus, http: HttpConfiguration) -> Union[str, None]:
    if status == DiscoveryStatus.SUCCEEDED:
        if http.port == 80:
            port = ""
        else:
            port = f":{http.port}"
        return f"{http.scheme}://{http.host}{port}" f"/discoveries" f"/{discovery_id}" f"/{discovery_id}.tar.gz"
    return None
