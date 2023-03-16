import logging
import os
import uuid
from enum import Enum
from pathlib import Path
from typing import Union, Any, Optional

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, BaseSettings
from starlette.exceptions import HTTPException

from simod_http.broker_client import BrokerClient, make_broker_client


def make_app() -> FastAPI:
    api = FastAPI()
    api.state.app = Application.init()
    return api


class Error(BaseModel):
    message: str
    detail: Union[Any, None] = None


class RequestStatus(str, Enum):
    UNKNOWN = 'unknown'
    ACCEPTED = 'accepted'
    PENDING = 'pending'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'
    DELETED = 'deleted'


class NotificationMethod(str, Enum):
    HTTP = 'callback'
    EMAIL = 'email'


class NotificationSettings(BaseModel):
    method: Union[NotificationMethod, None] = None
    callback_url: Union[str, None] = None
    email: Union[str, None] = None


class Response(BaseModel):
    request_id: Union[str, None]
    request_status: Union[RequestStatus, None]
    error: Union[Error, None]
    archive_url: Union[str, None]

    def json_response(self, status_code: int) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content=self.dict(exclude_none=True),
        )

    @staticmethod
    def from_http_exception(exc: HTTPException) -> 'Response':
        return Response(
            error=Error(message=exc.detail),
        )


class JobRequest(BaseModel):
    id: str
    output_dir: Path
    status: Union[RequestStatus, None] = None
    configuration_path: Union[Path, None] = None
    archive_url: Union[str, None] = None
    timestamp: Union[pd.Timestamp, None] = None
    notification_settings: Union[NotificationSettings, None] = None
    notified: bool = False

    class Config:
        arbitrary_types_allowed = True

    def __str__(self):
        return f'JobRequest(' \
               f'id={self.id}, ' \
               f'output_dir={self.output_dir}, ' \
               f'status={self.status}, ' \
               f'configuration_path={self.configuration_path}, ' \
               f'archive_url={self.archive_url}, ' \
               f'timestamp={self.timestamp}, ' \
               f'notification_settings={self.notification_settings}, ' \
               f'notified={self.notified})'

    def save(self):
        request_info_path = self.output_dir / 'request.json'
        request_info_path.write_text(self.json(exclude={'event_log': True}))

    @staticmethod
    def empty(storage_path: Path) -> 'JobRequest':
        request_id = str(uuid.uuid4())

        output_dir = storage_path / 'requests' / request_id
        output_dir.mkdir(parents=True, exist_ok=True)

        return JobRequest(
            id=request_id,
            output_dir=output_dir.absolute(),
            status=RequestStatus.UNKNOWN,
            configuration_path=None,
            callback_endpoint=None,
            archive_url=None,
            timestamp=pd.Timestamp.now(),
        )


class PatchJobRequest(BaseModel):
    status: RequestStatus


class Application(BaseSettings):
    """
    Simod application that stores main settings and provides access to internal API.
    """

    logger = logging.getLogger('simod_http.application')

    # These host and port are used to compose a link to the resulting archive.
    simod_http_host: str = 'localhost'
    simod_http_port: int = 8000
    simod_http_scheme: str = 'http'

    # Path on the file system to store results until the user fetches them, or they expire.
    simod_http_storage_path: str = '/tmp/simod'
    simod_http_request_expiration_timedelta: int = 60 * 60 * 24 * 7  # 7 days
    simod_http_storage_cleaning_timedelta: int = 60

    # Logging levels: CRITICAL, FATAL, ERROR, WARNING, WARN, INFO, DEBUG, NOTSET
    simod_http_log_level: str = 'debug'
    simod_http_log_format = '%(asctime)s \t %(name)s \t %(levelname)s \t %(message)s'
    simod_http_log_path: Union[str, None] = None

    # Broker settings
    broker_url: str = 'amqp://guest:guest@localhost:5672/'
    simod_exchange_name: str = 'simod'
    simod_pending_routing_key: str = 'requests.status.pending'

    broker_client: Union[BrokerClient, None] = None

    class Config:
        env_file = '.env'

    def __init__(self, **data):
        super().__init__(**data)

        storage_path = Path(self.simod_http_storage_path)
        storage_path.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=self.simod_http_log_level.upper(),
            format=self.simod_http_log_format,
            filename=self.simod_http_log_path,
        )

        self.logger.info(f'Application initialized: {self}')

    @staticmethod
    def init() -> 'Application':
        debug = os.environ.get('SIMOD_HTTP_DEBUG', 'false').lower() == 'true'

        if debug:
            app = Application()
        else:
            app = Application(_env_file='.env.production')

        app.simod_http_storage_path = Path(app.simod_http_storage_path)

        client = make_broker_client(app.broker_url, app.simod_exchange_name, app.simod_pending_routing_key)
        app.broker_client = client
        app.logger.info(f'Broker client initialized: {app.broker_client}')

        return app

    def load_request(self, request_id: str) -> JobRequest:
        request_dir = Path(self.simod_http_storage_path) / 'requests' / request_id
        if not request_dir.exists():
            raise NotFound(
                request_id=request_id,
                request_status=RequestStatus.UNKNOWN,
                archive_url=None,
                message='Request not found',
            )

        request_info_path = request_dir / 'request.json'
        request = JobRequest.parse_raw(request_info_path.read_text())
        return request

    def new_request_from_params(self, callback_url: Optional[str] = None, email: Optional[str] = None) -> 'JobRequest':
        request = JobRequest.empty(Path(self.simod_http_storage_path))

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

        request.notification_settings = notification_settings

        return request

    def make_results_url_for(self, request: JobRequest) -> Union[str, None]:
        if request.status == RequestStatus.SUCCEEDED:
            if self.simod_http_port == 80:
                port = ''
            else:
                port = f':{self.simod_http_port}'
            return f'{self.simod_http_scheme}://{self.simod_http_host}{port}' \
                   f'/discoveries' \
                   f'/{request.id}' \
                   f'/{request.id}.tar.gz'
        return None

    def publish_request(self, request: JobRequest):
        if self.broker_client is None:
            logging.error('Broker client is not initialized')
            raise InternalServerError(message='Broker client is not initialized')

        self.broker_client.publish_request(request.id)


class BaseRequestException(Exception):
    _status_code = 500

    request_id = None
    request_status = None
    archive_url = None
    message = 'Internal server error'

    def __init__(
            self,
            request_id: Union[str, None] = None,
            message: Union[str, None] = None,
            request_status: Union[RequestStatus, None] = None,
            archive_url: Union[str, None] = None,
    ):
        if request_id is not None:
            self.request_id = request_id
        if message is not None:
            self.message = message
        if request_status is not None:
            self.request_status = request_status
        if archive_url is not None:
            self.archive_url = archive_url

    @property
    def status_code(self) -> int:
        return self._status_code

    def make_response(self) -> Response:
        return Response(
            request_id=self.request_id,
            request_status=self.request_status,
            archive_url=self.archive_url,
            error=Error(message=self.message),
        )

    def json_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content=self.make_response().dict(exclude_none=True),
        )


class NotFound(BaseRequestException):
    _status_code = 404
    message = 'Not Found'


class BadMultipartRequest(BaseRequestException):
    _status_code = 400
    message = 'Bad Multipart Request'


class UnsupportedMediaType(BaseRequestException):
    _status_code = 415
    message = 'Unsupported Media Type'


class InternalServerError(BaseRequestException):
    _status_code = 500
    message = 'Internal Server Error'


class NotSupported(BaseRequestException):
    _status_code = 501
    message = 'Not Supported'
