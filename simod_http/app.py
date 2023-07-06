import logging
import os
from pathlib import Path
from typing import Union, Optional

from fastapi import FastAPI
from pydantic import BaseModel, BaseSettings
from pymongo import MongoClient

from simod_http.broker_client import BrokerClient, make_broker_client
from simod_http.configurations import HttpConfiguration, ApplicationConfiguration
from simod_http.exceptions import NotFound, InternalServerError
from simod_http.files_repository import FilesRepositoryInterface
from simod_http.files_repository_fs import FileSystemFilesRepository
from simod_http.discoveries import DiscoveryStatus, DiscoveryRequest
from simod_http.discoveries_repository import DiscoveriesRepositoryInterface
from simod_http.discoveries_repository_mongo import make_mongo_job_requests_repository


class PatchJobRequest(BaseModel):
    status: DiscoveryStatus


def make_results_url_for(request_id: str, status: DiscoveryStatus, http: HttpConfiguration) -> Union[str, None]:
    if status == DiscoveryStatus.SUCCEEDED:
        if http.port == 80:
            port = ""
        else:
            port = f":{http.port}"
        return f"{http.scheme}://{http.host}{port}" f"/discoveries" f"/{request_id}" f"/{request_id}.tar.gz"
    return None


class Application:
    configuration: ApplicationConfiguration
    logger = logging.getLogger("simod_http.application")

    # Initialization of the fields below happens only once, when a property is accessed for the first time
    _files_repository: FilesRepositoryInterface
    _discoveries_repository: DiscoveriesRepositoryInterface
    _broker_client: BrokerClient
    _mongo_client: MongoClient

    def __init__(self, configuration: ApplicationConfiguration):
        self.configuration = configuration

    @property
    def broker_client(self) -> BrokerClient:
        if self._broker_client is None:
            self._broker_client = make_broker_client(
                self.configuration.broker.url,
                self.configuration.broker.exchange_name,
                self.configuration.broker.pending_routing_key,
            )
        return self._broker_client

    @property
    def mongo_client(self) -> MongoClient:
        if self._mongo_client is None:
            self._mongo_client = MongoClient(
                self.configuration.mongo.url, username="root", password="example"
            )  # TODO: refactor credentials
        return self._mongo_client

    @property
    def files_repository(self) -> FilesRepositoryInterface:
        if self._files_repository is None:
            self._files_repository = FileSystemFilesRepository(self.configuration.storage.files_path)
        return self._files_repository

    @property
    def discoveries_repository(self) -> DiscoveriesRepositoryInterface:
        if self._discoveries_repository is None:
            self._discoveries_repository = make_mongo_job_requests_repository(
                self.mongo_client,
                self.configuration.mongo.database_name,
                self.configuration.mongo.discoveries_collection,
            )
        return self._discoveries_repository

    def close(self):
        if self._broker_client is not None:
            self._broker_client.close()
        if self._mongo_client is not None:
            self._mongo_client.close()
