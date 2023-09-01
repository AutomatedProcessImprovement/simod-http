import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union


class DiscoveryStatus(str, Enum):
    UNKNOWN = "unknown"  # default
    ACCEPTED = "accepted"  # incoming request has been accepted and discovery job has been created
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"  # error during execution
    EXPIRED = "expired"  # expiration time reached
    DELETED = "deleted"  # files deleted


class NotificationMethod(str, Enum):
    HTTP = "callback"
    EMAIL = "email"


@dataclass
class NotificationSettings:
    method: Union[NotificationMethod, None] = None
    callback_url: Union[str, None] = None
    email: Union[str, None] = None


@dataclass
class Discovery:
    configuration_path: str
    status: DiscoveryStatus = DiscoveryStatus.UNKNOWN
    _id: Optional[str] = None  # MongoDB ObjectId
    output_dir: Optional[str] = None
    notification_settings: Optional[NotificationSettings] = None
    created_timestamp: Optional[datetime.datetime] = None
    started_timestamp: Optional[datetime.datetime] = None
    finished_timestamp: Optional[datetime.datetime] = None
    archive_url: Optional[str] = None
    notified: bool = False

    @property
    def id(self):
        return self._id

    def __post_init__(self):
        self._id = str(self._id) if self._id else None

    def set_id(self, discovery_id: str):
        self._id = str(discovery_id)

    def to_mongo_dict(self, without_id: bool = False):
        d = {
            "configuration_path": self.configuration_path,
            "notification_settings": self.notification_settings if self.notification_settings else None,
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


def remove_none_values_from_dict(d: dict):
    for key, value in list(d.items()):
        if value is None:
            del d[key]
        elif isinstance(value, dict):
            remove_none_values_from_dict(value)
