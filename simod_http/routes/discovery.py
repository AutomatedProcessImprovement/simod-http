from dataclasses import dataclass
from pathlib import Path
from typing import Union

from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import FileResponse, Response

from simod_http.app import Application
from simod_http.configurations import HttpConfiguration
from simod_http.discoveries.model import Discovery, DiscoveryStatus
from simod_http.exceptions import InternalServerError, NotFound

router = APIRouter(prefix="/discoveries")


@router.get("/{discovery_id}")
async def get_discovery(request: Request, discovery_id: str) -> Discovery:
    """
    Get the status of the discovery.
    """
    app = request.app.state.app

    return await _get_discovery(app, discovery_id)


@dataclass
class PatchDiscoveryPayload:
    status: DiscoveryStatus


@router.get("/{discovery_id}/configuration")
async def get_discovery_configuration(request: Request, discovery_id: str) -> FileResponse:
    """
    Get the configuration of the discovery.
    """
    app = request.app.state.app

    discovery = await _get_discovery(app, discovery_id)

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
async def get_discovery_file(request: Request, discovery_id: str, file_name: str) -> Response:
    """
    Get a file for the discovery.
    """
    app = request.app.state.app

    discovery = await _get_discovery(app, discovery_id)

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


@router.patch("/{discovery_id}")
async def patch_discovery(request: Request, discovery_id: str, payload: PatchDiscoveryPayload) -> Discovery:
    """
    Update the status of the discovery.
    """
    app = request.app.state.app

    try:
        archive_url = None
        if payload.status == DiscoveryStatus.SUCCEEDED:
            archive_url = _make_results_url_for(discovery_id, payload.status, app.configuration.http)

        app.discoveries_repository.save_status(discovery_id, payload.status, archive_url)
    except Exception as e:
        raise InternalServerError(
            discovery_id=discovery_id,
            message=f"Failed to update discovery {discovery_id}: {e}",
        )

    return await _get_discovery(app, discovery_id)


@dataclass
class DeleteDiscoveryResponse:
    id: str
    status: DiscoveryStatus = DiscoveryStatus.DELETED


@router.delete("/{discovery_id}")
async def delete_discovery(request: Request, discovery_id: str) -> DeleteDiscoveryResponse:
    app = request.app.state.app

    discovery = await _get_discovery(app, discovery_id)

    discovery.status = DiscoveryStatus.DELETED
    app.discoveries_repository.save_status(discovery_id, discovery.status)

    return DeleteDiscoveryResponse(id=discovery_id, status=discovery.status)


async def _get_discovery(app: Application, discovery_id: str) -> Discovery:
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


def _make_results_url_for(discovery_id: str, status: DiscoveryStatus, http: HttpConfiguration) -> Union[str, None]:
    if status == DiscoveryStatus.SUCCEEDED:
        if http.port == 80:
            port = ""
        else:
            port = f":{http.port}"
        return f"{http.scheme}://{http.host}{port}" f"/discoveries" f"/{discovery_id}" f"/{discovery_id}.tar.gz"
    return None
