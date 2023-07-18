import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel


class DiscoveryStatus(str, Enum):
    UNKNOWN = "unknown"
    ACCEPTED = "accepted"
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DELETED = "deleted"


class NotificationMethod(str, Enum):
    HTTP = "callback"
    EMAIL = "email"


class NotificationSettings(BaseModel):
    method: Union[NotificationMethod, None] = None
    callback_url: Union[str, None] = None
    email: Union[str, None] = None


@dataclass
class Discovery:
    configuration_path: str
    status: DiscoveryStatus
    _id: Optional[str] = None  # MongoDB ObjectId
    id: Optional[str] = None  # Same as _id, but for returning in Response, _<field> are ignored
    output_dir: Optional[str] = None
    notification_settings: Optional[NotificationSettings] = None
    created_timestamp: Optional[datetime.datetime] = None
    started_timestamp: Optional[datetime.datetime] = None
    finished_timestamp: Optional[datetime.datetime] = None
    archive_url: Optional[str] = None
    notified: bool = False

    def __post_init__(self):
        self.id = str(self._id) if self._id else None

    def set_id(self, discovery_id: str):
        self._id = discovery_id
        self.id = self._id

    def to_dict(self, without_id: bool = False):
        d = {
            "configuration_path": self.configuration_path,
            "notification_settings": self.notification_settings.dict(exclude_none=True)
            if self.notification_settings
            else None,
            "status": self.status,
            "_id": self._id,
            "output_dir": self.output_dir,
            "created_timestamp": self.created_timestamp,
            "started_timestamp": self.started_timestamp,
            "finished_timestamp": self.finished_timestamp,
            "archive_url": self.archive_url,
            "notified": self.notified,
        }

        remove_none_values_from_dict(d)

        if without_id:
            del d["_id"]

        return d


@dataclass
class DiscoveryOut:
    """
    This class is used to return a Discovery in the response without the _id field and other fields that are not needed.
    """

    id: Optional[str]
    status: DiscoveryStatus
    created_timestamp: Optional[datetime.datetime]
    started_timestamp: Optional[datetime.datetime]
    finished_timestamp: Optional[datetime.datetime]
    archive_url: Optional[str]


def remove_none_values_from_dict(d: dict):
    for key, value in list(d.items()):
        if value is None:
            del d[key]
        elif isinstance(value, dict):
            remove_none_values_from_dict(value)
