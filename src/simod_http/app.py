import logging
import os
from pathlib import Path
from typing import Union

from fastapi import FastAPI
from pydantic import BaseModel, BaseSettings
from pymongo import MongoClient

from simod_http.broker_client import BrokerClient, make_broker_client
from simod_http.exceptions import NotFound, InternalServerError
from simod_http.files_repository import FilesRepositoryInterface
from simod_http.files_repository_fs import FileSystemFilesRepository
from simod_http.requests import RequestStatus, JobRequest
from simod_http.requests_repository import JobRequestsRepositoryInterface
from simod_http.requests_repository_mongo import make_mongo_job_requests_repository


def make_app() -> FastAPI:
    api = FastAPI()
    api.state.app = Application.init()
    return api


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
    simod_http_storage_path: Union[str, None] = None
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

    # Repositories settings
    mongo_url: str = 'mongodb://localhost:27017/'
    mongo_database: str = 'simod'
    mongo_requests_collection: str = 'requests'
    mongo_username: str = 'root'
    mongo_password: str = 'example'

    files_repository: Union[FilesRepositoryInterface, None] = None
    job_requests_repository: Union[JobRequestsRepositoryInterface, None] = None

    # Derived storage paths
    files_storage_path: Union[Path, None] = None
    requests_storage_path: Union[Path, None] = None

    class Config:
        env_file = '.env'

    def __init__(self, **data):
        super().__init__(**data)

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

        app.simod_http_storage_path = os.environ.get('SIMOD_HTTP_STORAGE_PATH', './data')

        app.files_storage_path = Path(app.simod_http_storage_path) / 'files'
        app.requests_storage_path = Path(app.simod_http_storage_path) / 'requests'
        app.files_storage_path.mkdir(parents=True, exist_ok=True)
        app.requests_storage_path.mkdir(parents=True, exist_ok=True)

        broker_client = make_broker_client(app.broker_url, app.simod_exchange_name, app.simod_pending_routing_key)
        app.broker_client = broker_client
        app.logger.info(f'Broker client initialized: {app.broker_client}')

        mongo_client = MongoClient(
            app.mongo_url,
            username=app.mongo_username,
            password=app.mongo_password,
        )

        files_repository = FileSystemFilesRepository(
            files_storage_path=app.files_storage_path,
        )
        app.files_repository = files_repository

        job_requests_repository = make_mongo_job_requests_repository(
            mongo_client=mongo_client,
            database=app.mongo_database,
            collection=app.mongo_requests_collection,
        )
        app.job_requests_repository = job_requests_repository

        return app

    def load_request(self, request_id: str) -> JobRequest:
        result = self.job_requests_repository.get(request_id)

        if result is None:
            raise NotFound(message='Request not found', request_id=request_id)

        return result

    def make_results_url_for(self, request: JobRequest) -> Union[str, None]:
        if request.status == RequestStatus.SUCCEEDED:
            if self.simod_http_port == 80:
                port = ''
            else:
                port = f':{self.simod_http_port}'
            return f'{self.simod_http_scheme}://{self.simod_http_host}{port}' \
                   f'/discoveries' \
                   f'/{request.get_id()}' \
                   f'/{request.get_id()}.tar.gz'
        return None

    def publish_request(self, request: JobRequest):
        if self.broker_client is None:
            logging.error('Broker client is not initialized')
            raise InternalServerError(message='Broker client is not initialized')

        self.broker_client.basic_publish_request(request.get_id())


