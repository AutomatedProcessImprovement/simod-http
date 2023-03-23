import logging
import re
import shutil
from pathlib import Path
from typing import Union, Optional, List

from fastapi import Response, Form
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.background import BackgroundTasks
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from uvicorn.config import LOGGING_CONFIG

from simod_http.app import PatchJobRequest
from simod_http.app import make_app, Application
from simod_http.exceptions import NotFound, BadMultipartRequest, UnsupportedMediaType, InternalServerError, NotSupported
from simod_http.requests import JobRequest, RequestStatus, NotificationMethod, NotificationSettings
from simod_http.responses import Response as AppResponse

api = make_app()

logging_config = LOGGING_CONFIG
logging_config['formatters']['default']['fmt'] = api.state.app.simod_http_log_format
logging_config['formatters']['access']['fmt'] = api.state.app.simod_http_log_format.replace(
    '%(message)s', '%(client_addr)s - "%(request_line)s" %(status_code)s')


# Routes: /

@api.get('/')
async def root() -> JSONResponse:
    raise NotFound()


@api.get('/{any_str}')
async def catch_all_route() -> JSONResponse:
    raise NotFound()


# Routes: /discoveries

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
    global api

    app: Application = api.state.app

    if email is not None:
        raise NotSupported(message='Email notifications are not supported')

    notification_settings = _notification_settings_from_params(callback_url, email)
    event_log_path = _save_uploaded_event_log(event_log)
    configuration_path = _update_and_save_configuration(configuration, event_log_path)

    request = JobRequest(
        notification_settings=notification_settings,
        configuration_path=str(configuration_path),
        status=RequestStatus.ACCEPTED,
        output_dir=None,
    )

    request = app.job_requests_repository.create(request, app.requests_storage_path)
    app.logger.info(f'New request {request.get_id()}: status={request.status}')

    background_tasks.add_task(_process_post_request, request)

    response = AppResponse(request_id=request.get_id(), request_status=request.status)
    return response.json_response(status_code=202)


@api.delete("/discoveries")
async def delete_discoveries() -> JSONResponse:
    """
    Delete all business process simulation model discovery requests.
    """
    app = api.state.app

    requests = app.job_requests_repository.get_all()

    try:
        _remove_fs_directories(requests)
    except Exception as e:
        raise InternalServerError(
            request_id=None,
            message=f'Failed to remove directories of requests: {e}'
        )

    deleted_amount = app.job_requests_repository.delete_all()

    return JSONResponse(status_code=200, content={'deleted_amount': deleted_amount})


# Routes: /discoveries/{request_id}

@api.get("/discoveries/{request_id}/configuration")
async def read_discovery_configuration(request_id: str) -> Response:
    """
    Get the configuration of the request.
    """
    try:
        request = api.state.app.load_request(request_id)
    except NotFound as e:
        raise e
    except Exception as e:
        raise InternalServerError(
            request_id=request_id,
            message=f'Failed to load request {request_id}: {e}',
        )

    if not request.configuration_path:
        raise InternalServerError(
            request_id=request_id,
            request_status=request.status,
            message=f'Request {request_id} has no configuration file',
        )

    file_path = Path(request.configuration_path)
    if not file_path.exists():
        raise NotFound(
            request_id=request_id,
            request_status=request.status,
            message=f"File not found: {file_path}",
        )

    media_type = _infer_media_type_from_extension(file_path.name)

    return Response(
        content=file_path.read_bytes(),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file_path.name}"',
        },
    )


@api.get("/discoveries/{request_id}/{file_name}")
async def read_discovery_file(request_id: str, file_name: str):
    """
    Get a file from a discovery request.
    """
    try:
        request = api.state.app.load_request(request_id)
    except NotFound as e:
        raise e
    except Exception as e:
        raise InternalServerError(
            request_id=request_id,
            message=f'Failed to load request {request_id}: {e}',
        )

    if not request.output_dir:
        raise InternalServerError(
            request_id=request_id,
            request_status=request.status,
            message=f'Request {request_id} has no output directory',
        )

    file_path = Path(request.output_dir) / file_name
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


@api.get("/discoveries/{request_id}")
async def read_discovery(request_id: str) -> JobRequest:
    """
    Get the status of the request.
    """
    try:
        request = api.state.app.load_request(request_id)
    except NotFound as e:
        raise e
    except Exception as e:
        raise InternalServerError(
            request_id=request_id,
            message=f'Failed to load request {request_id}: {e}',
        )

    return request


@api.patch("/discoveries/{request_id}")
async def patch_discovery(request_id: str, patch_request: PatchJobRequest) -> JSONResponse:
    """
    Update the status of the request.
    """
    app = api.state.app

    try:
        archive_url = None
        if patch_request.status == RequestStatus.SUCCEEDED:
            archive_url = app.make_results_url_for(request_id)

        app.job_requests_repository.save_status(request_id, patch_request.status, archive_url)
    except Exception as e:
        raise InternalServerError(
            request_id=request_id,
            message=f'Failed to update request {request_id}: {e}',
        )

    return AppResponse(
        request_id=request_id,
        request_status=patch_request.status,
    ).json_response(status_code=200)


@api.delete("/discoveries/{request_id}")
async def delete_discovery(request_id: str) -> JSONResponse:
    global api

    app = api.state.app

    try:
        request = app.load_request(request_id)
    except NotFound as e:
        raise e
    except Exception as e:
        raise InternalServerError(
            request_id=request_id,
            message=f'Failed to load request {request_id}: {e}',
        )

    request.status = RequestStatus.DELETED
    app.job_requests_repository.save_status(request_id, request.status)

    return AppResponse(
        request_id=request_id,
        request_status=RequestStatus.DELETED,
    ).json_response(status_code=200)


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
    elif file_name.endswith('.yaml') or file_name.endswith('.yml'):
        media_type = 'text/yaml'
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


def _save_uploaded_event_log(upload: UploadFile) -> Path:
    global api

    app: Application = api.state.app

    event_log_file_extension = _infer_event_log_file_extension_from_header(upload.content_type)
    if event_log_file_extension is None:
        raise UnsupportedMediaType(message="Unsupported event log file type")

    content = upload.file.read()
    upload.file.close()

    event_log_file = app.files_repository.create(content, event_log_file_extension)
    event_log_file_path = app.files_repository.file_path(event_log_file.file_name)
    app.logger.info(f'Uploaded event log file: {event_log_file_path}')

    return app.files_repository.file_path(event_log_file.file_name)


def _update_and_save_configuration(upload: UploadFile, event_log_path: Path):
    global api

    app: Application = api.state.app

    content = upload.file.read()
    upload.file.close()

    regexp = r'log_path: .*\n'
    replacement = f'log_path: {event_log_path.absolute()}\n'
    content = re.sub(regexp, replacement, content.decode('utf-8'))

    # test log is not supported in request params
    regexp = r'test_log_path: .*\n'
    replacement = 'test_log_path: None\n'
    content = re.sub(regexp, replacement, content)

    new_file = app.files_repository.create(content.encode('utf-8'), '.yaml')
    new_file_path = app.files_repository.file_path(new_file.file_name)
    app.logger.info(f'Uploaded configuration file: {new_file_path}')

    return new_file_path


def _process_post_request(request: JobRequest):
    global api

    app: Application = api.state.app

    app.logger.info(f'Processing request {request.get_id()}: '
                    f'status={request.status}, '
                    f'configuration_path={request.configuration_path}')

    try:
        api.state.app.publish_request(request)
        request.status = RequestStatus.PENDING
        app.job_requests_repository.save(request)
    except Exception as e:
        request.status = RequestStatus.FAILED
        app.job_requests_repository.save(request)
        app.logger.error(e)
        raise e

    app.logger.info(f'Processed request {request.get_id()}, {request.status}')


def _save_event_log(event_log: UploadFile, request: JobRequest):
    event_log_file_extension = _infer_event_log_file_extension_from_header(event_log.content_type)
    if event_log_file_extension is None:
        raise UnsupportedMediaType(message="Unsupported event log file type")

    event_log_path = Path(request.output_dir) / f"event_log{event_log_file_extension}"
    event_log_path.write_bytes(event_log.file.read())

    return event_log_path


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

    configuration_path = Path(request.output_dir) / 'configuration.yaml'
    configuration_path.write_text(data)

    return configuration_path


def _infer_event_log_file_extension_from_header(content_type: str) -> Union[str, None]:
    if "text/csv" in content_type:
        return ".csv"
    elif "application/xml" in content_type or "text/xml" in content_type:
        return ".xml"
    else:
        return None


def _remove_fs_directories(requests: List[JobRequest]):
    for request in requests:
        if request.output_dir:
            output_dir = Path(request.output_dir)
            if output_dir.exists():
                shutil.rmtree(output_dir)


@api.on_event('startup')
async def application_startup():
    global api

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


@api.exception_handler(HTTPException)
async def request_exception_handler(_, exc: HTTPException) -> JSONResponse:
    global api

    app = api.state.app

    app.logger.exception(f'Request exception occurred: {exc}')
    return JSONResponse(
        status_code=exc.status_code,
        content={
            'error': {'message': exc.detail},
        },
    )


@api.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    global api

    app = api.state.app

    app.logger.exception(f'Validation exception occurred: {exc}')
    return JSONResponse(
        status_code=422,
        content={
            'error': exc.errors(),
        },
    )


@api.exception_handler(NotFound)
async def not_found_exception_handler(_, exc: NotFound) -> JSONResponse:
    return exc.json_response()


@api.exception_handler(BadMultipartRequest)
async def bad_multipart_exception_handler(_, exc: BadMultipartRequest) -> JSONResponse:
    global api

    app = api.state.app

    app.logger.exception(f'Bad multipart exception occurred: {exc}')
    return exc.json_response()


@api.exception_handler(UnsupportedMediaType)
async def bad_multipart_exception_handler(_, exc: UnsupportedMediaType) -> JSONResponse:
    global api

    app = api.state.app

    app.logger.exception(f'Unsupported media type exception occurred: {exc}')
    return exc.json_response()


@api.exception_handler(InternalServerError)
async def bad_multipart_exception_handler(_, exc: InternalServerError) -> JSONResponse:
    global api

    app = api.state.app

    app.logger.exception(f'Internal server error exception occurred: {exc}')
    return exc.json_response()


@api.exception_handler(NotSupported)
async def bad_multipart_exception_handler(_, exc: NotSupported) -> JSONResponse:
    global api

    app = api.state.app

    app.logger.exception(f'Not supported exception occurred: {exc}')
    return exc.json_response()


@api.exception_handler(Exception)
async def exception_handler(_, exc: Exception) -> JSONResponse:
    global api

    app = api.state.app

    app.logger.exception(f'Exception occurred: {exc}')
    return JSONResponse(
        status_code=500,
        content={
            'error': {'message': 'Internal Server Error'},
        },
    )
