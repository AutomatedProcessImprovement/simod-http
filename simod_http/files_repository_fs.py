from pathlib import Path
from typing import Optional

from simod_http.files_repository import FilesRepositoryInterface, File, compute_sha256


class FileSystemFilesRepository(FilesRepositoryInterface):

    def __init__(self, files_storage_path: Path):
        self.files_storage_path = files_storage_path
        self.files_storage_path.mkdir(parents=True, exist_ok=True)

    def file_path(self, file_name: str) -> Path:
        return self.files_storage_path / file_name

    def create(self, content: bytes, suffix: str) -> File:
        file_hash = compute_sha256(content)
        file_name = f'{file_hash}{suffix}'

        new_file = File(
            file_name=file_name,
            content=content,
            sha256=file_hash,
            _id=file_hash,
        )

        file_path = self.file_path(file_name)
        if not file_path.exists():
            file_path.write_bytes(content)

        return new_file

    def get_by_id(self, file_id: str) -> Optional[File]:
        return self.get_by_sha256(file_id)

    def get_by_sha256(self, sha256: str) -> Optional[File]:
        for file in self.files_storage_path.iterdir():
            if file.stem == sha256:
                return File(
                    file_name=file.name,
                    content=file.read_bytes(),
                    sha256=sha256,
                    _id=sha256,
                )

        return None

    def does_exist(self, sha256: str) -> bool:
        return self.get_by_sha256(sha256) is not None

    def delete(self, file_id: str):
        found_file = self.get_by_id(file_id)
        if found_file is not None:
            file_path = self.file_path(found_file.file_name)
            file_path.unlink()
