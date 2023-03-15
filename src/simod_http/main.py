import logging
import re
import shutil
from pathlib import Path
from typing import Union, Optional

import pandas as pd
from fastapi import FastAPI
from fastapi import Response, Form
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi_utils.tasks import repeat_every
from starlette.background import BackgroundTasks
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from uvicorn.config import LOGGING_CONFIG

from simod_http.app import Response, BadMultipartRequest, \
    InternalServerError, Application
from simod_http.app import Response as AppResponse, RequestStatus, NotFound, UnsupportedMediaType, NotSupported, \
    JobRequest, PatchJobRequest

api = FastAPI()
api.state.app = Application.init()

logging_config = LOGGING_CONFIG
logging_config['formatters']['default']['fmt'] = api.state.app.simod_http_log_format
logging_config['formatters']['access']['fmt'] = api.state.app.simod_http_log_format.replace(
    '%(message)s', '%(client_addr)s - "%(request_line)s" %(status_code)s')


@api.get('/{any_str}')
async def root() -> Response:
    raise NotFound()


@api.get("/discoveries/{request_id}/{file_name}")
async def read_discovery_file(request_id: str, file_name: str):
    """
    Get a file from a discovery request.
    """
    request = api.state.app.load_request(request_id)

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


@api.get("/discoveries/{request_id}")
async def read_discovery(request_id: str) -> AppResponse:
    """
    Get the status of the request.
    """
    request = api.state.app.load_request(request_id)

    return AppResponse(
        request_id=request_id,
        request_status=request.status,
        archive_url=app.make_results_url_for(request),
    )


@api.patch("/discoveries/{request_id}")
async def patch_discovery(request_id: str, patch_request: PatchJobRequest) -> AppResponse:
    """
    Update the status of the request.
    """
    request = api.state.app.load_request(request_id)

    request.status = patch_request.status
    request.save()

    return AppResponse(
        request_id=request_id,
        request_status=request.status,
        archive_url=app.make_results_url_for(request),
    )


@api.post("/discoveries")
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
    request = api.state.app.new_request_from_params(callback_url, email)

    if email is not None:
        request.status = RequestStatus.FAILED
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
        api.state.app.publish_request(request)
        request.status = RequestStatus.PENDING
    except Exception as e:
        request.status = RequestStatus.FAILED
        logging.error(e)
        raise e
    finally:
        request.save()

    logging.info(f'Processed request {request.id}, {request.status}')


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


@api.delete("/discoveries/{request_id}")
async def delete_discovery(request_id: str) -> AppResponse:
    request = api.state.app.load_request(request_id)

    logging.info(f'Deleting request: {request.id}, {request.status}')
    shutil.rmtree(request.output_dir, ignore_errors=True)

    return AppResponse(
        request_id=request_id,
        request_status=RequestStatus.DELETED,
        archive_url=None,
    )


@api.on_event('startup')
async def application_startup():
    app = api.state.app

    logging_handlers = []
    if api.state.app.simod_http_log_path is not None:
        logging_handlers.append(logging.FileHandler(app.simod_http_log_path, mode='w'))

    if len(logging_handlers) > 0:
        logging.basicConfig(
            level=app.simod_http_log_level.upper(),
            handlers=logging_handlers,
            format=app.simod_http_log_format,
        )
    else:
        logging.basicConfig(
            level=app.simod_http_log_level.upper(),
            format=app.simod_http_log_format,
        )

    logging.debug(f'Application settings: {api.state.app.__dict__}')


@api.on_event('shutdown')
async def application_shutdown():
    requests_dir = Path(api.state.app.simod_http_storage_path) / 'requests'

    if not requests_dir.exists():
        return

    for request_dir in requests_dir.iterdir():
        logging.debug(f'Checking request directory before shutting down: {request_dir}')

        await _remove_empty_or_orphaned_request_dir(request_dir)

        try:
            request = api.state.app.load_request(request_dir.name)
        except Exception as e:
            logging.error(f'Failed to load request: {request_dir.name}, {str(e)}')
            continue

        # At the end, there are only 'failed' or 'succeeded' requests
        if request.status not in [RequestStatus.SUCCEEDED, RequestStatus.FAILED]:
            request.status = RequestStatus.FAILED
            request.timestamp = pd.Timestamp.now()
            request.save()


@api.on_event('startup')
@repeat_every(seconds=api.state.app.simod_http_storage_cleaning_timedelta)
async def clean_up():
    app = api.state.app
    requests_dir = Path(api.state.app.simod_http_storage_path) / 'requests'

    if not requests_dir.exists():
        return

    current_timestamp = pd.Timestamp.now()
    expire_after_delta = pd.Timedelta(seconds=app.simod_http_request_expiration_timedelta)

    for request_dir in requests_dir.iterdir():
        if request_dir.is_dir():
            logging.debug(f'Checking request directory for expired data: {request_dir}')

            await _remove_empty_or_orphaned_request_dir(request_dir)

            try:
                request = app.load_request(request_dir.name)
            except Exception as e:
                logging.error(f'Failed to load request: {request_dir.name}, {str(e)}')
                continue

            await _remove_expired_requests(current_timestamp, expire_after_delta, request, request_dir)

            await _remove_not_running_not_timestamped_requests(request, request_dir)


async def _remove_not_running_not_timestamped_requests(request: JobRequest, request_dir: Path):
    # Removes requests without timestamp that are not running
    if request.timestamp is None and request.status not in [RequestStatus.ACCEPTED, RequestStatus.RUNNING]:
        logging.info(f'Removing request folder for {request_dir.name}, no timestamp and not running')
        shutil.rmtree(request_dir, ignore_errors=True)


async def _remove_expired_requests(
        current_timestamp: pd.Timestamp,
        expire_after_delta: pd.Timedelta,
        request: JobRequest,
        request_dir: Path,
):
    if request.status in [RequestStatus.UNKNOWN, RequestStatus.SUCCEEDED, RequestStatus.FAILED]:
        expired_at = request.timestamp + expire_after_delta
        if expired_at <= current_timestamp:
            logging.info(f'Removing request folder for {request_dir.name}, expired at {expired_at}')
            shutil.rmtree(request_dir, ignore_errors=True)


async def _remove_empty_or_orphaned_request_dir(request_dir):
    if request_dir.is_file():
        return

    # Removes empty directories
    if len(list(request_dir.iterdir())) == 0:
        logging.info(f'Removing empty directory: {request_dir}')
        shutil.rmtree(request_dir, ignore_errors=True)

    # Removes orphaned request directories
    if not (request_dir / 'request.json').exists():
        logging.info(f'Removing request folder for {request_dir.name}, no request.json file')
        shutil.rmtree(request_dir, ignore_errors=True)


@api.exception_handler(HTTPException)
async def request_exception_handler(_, exc: HTTPException) -> JSONResponse:
    logging.exception(f'Request exception occurred: {exc}')
    return JSONResponse(
        status_code=exc.status_code,
        content={
            'error': {'message': exc.detail},
        },
    )


@api.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    logging.exception(f'Validation exception occurred: {exc}')
    return JSONResponse(
        status_code=422,
        content={
            'error': {'message': 'Validation error', 'detail': exc.errors()},
        },
    )


@api.exception_handler(NotFound)
async def not_found_exception_handler(_, exc: NotFound) -> JSONResponse:
    return exc.json_response()


@api.exception_handler(BadMultipartRequest)
async def bad_multipart_exception_handler(_, exc: BadMultipartRequest) -> JSONResponse:
    logging.exception(f'Bad multipart exception occurred: {exc}')
    return exc.json_response()


@api.exception_handler(UnsupportedMediaType)
async def bad_multipart_exception_handler(_, exc: UnsupportedMediaType) -> JSONResponse:
    logging.exception(f'Unsupported media type exception occurred: {exc}')
    return exc.json_response()


@api.exception_handler(InternalServerError)
async def bad_multipart_exception_handler(_, exc: InternalServerError) -> JSONResponse:
    logging.exception(f'Internal server error exception occurred: {exc}')
    return exc.json_response()


@api.exception_handler(NotSupported)
async def bad_multipart_exception_handler(_, exc: NotSupported) -> JSONResponse:
    logging.exception(f'Not supported exception occurred: {exc}')
    return exc.json_response()
