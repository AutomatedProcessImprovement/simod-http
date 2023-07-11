from dataclasses import dataclass
from typing import Optional


@dataclass
class File:
    file_name: str
    content: bytes
    sha256: str
    _id: Optional[str] = None
