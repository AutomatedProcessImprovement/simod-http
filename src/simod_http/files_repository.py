import hashlib
from abc import abstractmethod, ABCMeta
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class File:
    filename: str
    content: bytes
    sha256: str
    _id: Optional[str] = None


class FilesRepositoryInterface(metaclass=ABCMeta):
    @abstractmethod
    def file_path(self, file_name: str) -> Path:
        pass

    @abstractmethod
    def create(self, content: bytes, suffix: str) -> File:
        pass

    @abstractmethod
    def get_by_id(self, file_id: str) -> Optional[File]:
        pass

    @abstractmethod
    def get_by_sha256(self, sha256: str) -> Optional[File]:
        pass

    @abstractmethod
    def does_exist(self, sha256: str) -> bool:
        pass

    @abstractmethod
    def delete(self, file_id: str):
        pass


class FilesRepository:
    def __init__(self, repository_store: FilesRepositoryInterface):
        self.repository_store = repository_store

    def create(self, content: bytes, suffix: str) -> File:
        return self.repository_store.create(content, suffix)

    def get_by_id(self, file_id: str) -> File:
        return self.repository_store.get_by_id(file_id)

    def get_by_sha256(self, sha256: str) -> File:
        return self.repository_store.get_by_sha256(sha256)

    def does_exist(self, sha256: str) -> bool:
        return self.repository_store.does_exist(sha256)

    def delete(self, file_id: str):
        self.repository_store.delete(file_id)


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
