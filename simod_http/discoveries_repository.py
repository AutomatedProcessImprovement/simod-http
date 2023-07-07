from abc import abstractmethod, ABCMeta
from pathlib import Path
from typing import Optional, List

from simod_http.discoveries import Discovery


class DiscoveriesRepositoryInterface(metaclass=ABCMeta):
    @abstractmethod
    def create(self, discovery: Discovery, discoveries_storage_path: Path) -> Discovery:
        pass

    @abstractmethod
    def get(self, discovery_id: str) -> Optional[Discovery]:
        pass

    @abstractmethod
    def save(self, discovery: Discovery):
        pass

    @abstractmethod
    def save_status(self, discovery_id: str, status: str, archive_url: Optional[str] = None):
        pass

    @abstractmethod
    def delete(self, discovery_id: str):
        pass

    @abstractmethod
    def get_all(self) -> List[Discovery]:
        pass

    @abstractmethod
    def delete_all(self):
        pass
