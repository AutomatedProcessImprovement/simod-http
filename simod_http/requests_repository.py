from abc import abstractmethod, ABCMeta
from pathlib import Path
from typing import Optional, List

from simod_http.discoveries import DiscoveryRequest


class JobRequestsRepositoryInterface(metaclass=ABCMeta):
    @abstractmethod
    def create(self, request: DiscoveryRequest, requests_storage_path: Path) -> DiscoveryRequest:
        pass

    @abstractmethod
    def get(self, request_id: str) -> Optional[DiscoveryRequest]:
        pass

    @abstractmethod
    def save(self, request: DiscoveryRequest):
        pass

    @abstractmethod
    def save_status(self, request_id: str, status: str, archive_url: Optional[str] = None):
        pass

    @abstractmethod
    def delete(self, request_id: str):
        pass

    @abstractmethod
    def get_all(self) -> List[DiscoveryRequest]:
        pass

    @abstractmethod
    def delete_all(self):
        pass
