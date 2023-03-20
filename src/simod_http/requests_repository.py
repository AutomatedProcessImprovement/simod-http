from abc import abstractmethod, ABCMeta
from pathlib import Path
from typing import Optional

from simod_http.requests import JobRequest


class JobRequestsRepositoryInterface(metaclass=ABCMeta):
    @abstractmethod
    def create(self, request: JobRequest, requests_storage_path: Path) -> JobRequest:
        pass

    @abstractmethod
    def get(self, request_id: str) -> Optional[JobRequest]:
        pass

    @abstractmethod
    def save(self, request: JobRequest):
        pass

    @abstractmethod
    def delete(self, request_id: str):
        pass


class JobRequestsRepository:
    def __init__(self, repository_store: JobRequestsRepositoryInterface):
        self.repository_store = repository_store

    def create(self, request: JobRequest, requests_storage_path: Path) -> JobRequest:
        return self.repository_store.create(request, requests_storage_path)

    def get(self, request_id: str) -> JobRequest:
        return self.repository_store.get(request_id)

    def save(self, request: JobRequest):
        self.repository_store.save(request)

    def delete(self, request_id: str):
        self.repository_store.delete(request_id)
