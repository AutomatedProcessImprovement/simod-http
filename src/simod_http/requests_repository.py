from abc import abstractmethod, ABCMeta
from pathlib import Path
from typing import Optional, List

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
    def save_status(self, request_id: str, status: str, archive_url: Optional[str] = None):
        pass

    @abstractmethod
    def delete(self, request_id: str):
        pass

    @abstractmethod
    def get_all(self) -> List[JobRequest]:
        pass

    @abstractmethod
    def delete_all(self):
        pass
