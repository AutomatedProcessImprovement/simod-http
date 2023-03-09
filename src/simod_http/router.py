import logging
import re
from pathlib import Path
from typing import Union, Optional

from fastapi import Response, Form, APIRouter
from fastapi.responses import JSONResponse
from starlette.background import BackgroundTasks
from starlette.datastructures import UploadFile

from simod_http.app import Response as AppResponse, RequestStatus, NotFound, UnsupportedMediaType, NotSupported, app, \
    JobRequest, PatchJobRequest

router = APIRouter()


@router.get("/discoveries/{request_id}/{file_name}")
async def read_discovery_file(request_id: str, file_name: str):
    """
    Get a file from a discovery request.
    """
    request = app.load_request(request_id)

    file_path = request.output_dir / file_name
    if not file_path.exists():
        raise NotFound(
            request_id=request_id,
            request_status=request.status,
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


@router.get("/discoveries/{request_id}")
async def read_discovery(request_id: str) -> AppResponse:
    """
    Get the status of the request.
    """
    request = app.load_request(request_id)

    return AppResponse(
        request_id=request_id,
        request_status=request.status,
        archive_url=app.make_results_url_for(request),
    )


@router.patch("/discoveries/{request_id}")
async def update_discovery(request_id: str, patch_request: PatchJobRequest) -> AppResponse:
    """
    Update the status of the request.
    """
    request = app.load_request(request_id)

    request.status = patch_request.status
    request.save()

    return AppResponse(
        request_id=request_id,
        request_status=request.status,
        archive_url=app.make_results_url_for(request),
    )


@router.post("/discoveries")
async def create_discovery(
        background_tasks: BackgroundTasks,
        configuration=Form(),
        event_log=Form(),
        callback_url: Optional[str] = None,
        email: Optional[str] = None,
) -> JSONResponse:
    """
    Create a new business process simulation model discovery request.
    """
    request = app.new_request_from_params(callback_url, email)

    if email is not None:
        request.status = RequestStatus.FAILURE
        request.save()

        raise NotSupported(
            request_id=request.id,
            request_status=request.status,
            message='Email notifications are not supported',
        )

    request.status = RequestStatus.ACCEPTED
    request.save()

    logging.info(f'New request: {request.id}, {request.status}')

    background_tasks.add_task(process_post_request, configuration, event_log, request)

    response = AppResponse(request_id=request.id, request_status=request.status)
    return response.json_response(status_code=202)


def process_post_request(configuration: UploadFile, event_log: UploadFile, request: JobRequest):
    logging.info(f'Processing request: {request.id}, {request.status}')

    event_log_path = _save_event_log(event_log, request)
    logging.info(f'Processing request: {request.id}, {request.status}, event_log_path: {event_log_path}')

    configuration_path = _update_config_and_save(configuration, event_log_path, request)
    logging.info(f'Processing request: {request.id}, {request.status}, configuration_path: {configuration_path}')

    request.configuration_path = configuration_path.absolute()

    try:
        app.publish_request(request)
        request.status = RequestStatus.PENDING
    except Exception as e:
        request.status = RequestStatus.FAILURE
        logging.error(e)
    finally:
        request.save()
        logging.info(f'Processing request: {request.id}, {request.status}')


def _update_config_and_save(configuration: UploadFile, event_log_path: Path, request: JobRequest):
    data = configuration.file.read()
    configuration.file.close()

    # regexp to replace "log_path: .*" with "log_path: <path>"
    regexp = r'log_path: .*\n'
    replacement = f'log_path: {event_log_path.absolute()}\n'
    data = re.sub(regexp, replacement, data.decode('utf-8'))

    # test log is not supported in request params
    regexp = r'test_log_path: .*\n'
    replacement = 'test_log_path: None\n'
    data = re.sub(regexp, replacement, data)

    configuration_path = request.output_dir / 'configuration.yaml'
    configuration_path.write_text(data)

    return configuration_path


def _save_event_log(event_log, request):
    event_log_file_extension = _infer_event_log_file_extension_from_header(
        event_log.content_type
    )
    if event_log_file_extension is None:
        raise UnsupportedMediaType(
            request_id=request.id,
            request_status=request.status,
            archive_url=None,
            message="Unsupported event log file type",
        )
    event_log_path = request.output_dir / f"event_log{event_log_file_extension}"
    event_log_path.write_bytes(event_log.file.read())
    return event_log_path


def _infer_event_log_file_extension_from_header(content_type: str) -> Union[str, None]:
    if "text/csv" in content_type:
        return ".csv"
    elif "application/xml" in content_type or "text/xml" in content_type:
        return ".xml"
    else:
        return None


def _infer_media_type_from_extension(file_name) -> str:
    if file_name.endswith('.csv'):
        media_type = 'text/csv'
    elif file_name.endswith('.xml'):
        media_type = 'application/xml'
    elif file_name.endswith('.xes'):
        media_type = 'application/xml'
    elif file_name.endswith('.bpmn'):
        media_type = 'application/xml'
    elif file_name.endswith('.json'):
        media_type = 'application/json'
    elif file_name.endswith('.png'):
        media_type = 'image/png'
    elif file_name.endswith('.jpg') or file_name.endswith('.jpeg'):
        media_type = 'image/jpeg'
    elif file_name.endswith('.pdf'):
        media_type = 'application/pdf'
    elif file_name.endswith('.txt'):
        media_type = 'text/plain'
    elif file_name.endswith('.zip'):
        media_type = 'application/zip'
    elif file_name.endswith('.gz'):
        media_type = 'application/gzip'
    elif file_name.endswith('.tar'):
        media_type = 'application/tar'
    elif file_name.endswith('.tar.gz'):
        media_type = 'application/tar+gzip'
    elif file_name.endswith('.tar.bz2'):
        media_type = 'application/x-bzip2'
    else:
        media_type = 'application/octet-stream'

    return media_type
