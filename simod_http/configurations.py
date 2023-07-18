import os
from dataclasses import dataclass
from pathlib import Path
from typing import Union, Optional

from dotenv import load_dotenv
from pydantic import MongoDsn


@dataclass
class HttpConfiguration:
    host: str = "localhost"
    port: int = 8000
    scheme: str = "http"


@dataclass
class StorageConfiguration:
    # Path on the file system to store results until the user fetches them, or they expire
    path: Union[str, None] = None
    # How long to keep results on the file system before deleting them, in seconds
    discovery_expiration_timedelta: int = 60 * 60 * 24 * 7  # 7 days
    # How often to check for expired results, in seconds
    cleaning_timedelta: int = 60

    _files_path: Optional[Path] = None
    _discoveries_path: Optional[Path] = None

    def __post_init__(self):
        if self.path is None:
            raise ValueError("Storage path is not set")

        self._files_path = Path(self.path) / "files"
        self._discoveries_path = Path(self.path) / "discoveries"

        self._files_path.mkdir(parents=True, exist_ok=True)
        self._discoveries_path.mkdir(parents=True, exist_ok=True)

    @property
    def files_path(self) -> Path:
        return self._files_path

    @property
    def discoveries_path(self) -> Path:
        return self._discoveries_path


@dataclass
class LoggingConfiguration:
    # Logging levels: CRITICAL, FATAL, ERROR, WARNING, WARN, INFO, DEBUG, NOTSET
    level: str = "debug"
    format: str = "%(asctime)s \t %(name)s \t %(levelname)s \t %(message)s"
    path: Union[str, None] = None


@dataclass
class BrokerConfiguration:
    url: str = "amqp://guest:guest@localhost:5672/"
    exchange_name: str = "simod"
    queue_name: str = "discoveries"
    pending_routing_key: str = "discoveries.status.pending"


@dataclass
class MongoConfiguration:
    url: MongoDsn = "mongodb://localhost:27017"
    database: str = "simod"
    discoveries_collection: str = "discoveries"

    _database_name: Optional[str] = None


class ApplicationConfiguration:
    debug: bool
    http: HttpConfiguration
    storage: StorageConfiguration
    logging: LoggingConfiguration
    broker: BrokerConfiguration
    mongo: MongoConfiguration

    def __init__(self, dotenv_path: Union[str, Path] = ".env"):
        load_dotenv(dotenv_path=dotenv_path, verbose=True)

        self.debug = os.environ.get("SIMOD_DEBUG", "true").lower() == "true"

        self.http = HttpConfiguration(
            host=os.environ.get("SIMOD_HTTP_HOST", "localhost"),
            port=int(os.environ.get("SIMOD_HTTP_PORT", 8000)),
            scheme=os.environ.get("SIMOD_HTTP_SCHEME", "http"),
        )

        self.storage = StorageConfiguration(
            path=os.environ.get("SIMOD_STORAGE_PATH", "./tmp"),
            discovery_expiration_timedelta=int(os.environ.get("SIMOD_STORAGE_DISCOVERY_EXPIRATION_TIMEDELTA", 604800)),
            cleaning_timedelta=int(os.environ.get("SIMOD_STORAGE_CLEANING_TIMEDELTA", 60)),
        )

        self.logging = LoggingConfiguration(
            level=os.environ.get("SIMOD_LOGGING_LEVEL", "info"),
            format=os.environ.get("SIMOD_LOGGING_FORMAT", "%(asctime)s \t %(name)s \t %(levelname)s \t %(message)s"),
            path=os.environ.get("SIMOD_LOGGING_PATH", None),
        )

        self.broker = BrokerConfiguration(
            url=os.environ.get("SIMOD_BROKER_URL", "amqp://guest:guest@localhost:5672/"),
            exchange_name=os.environ.get("SIMOD_BROKER_EXCHANGE_NAME", "simod"),
            queue_name=os.environ.get("SIMOD_BROKER_QUEUE_NAME", "discoveries"),
            pending_routing_key=os.environ.get("SIMOD_BROKER_PENDING_ROUTING_KEY", "discoveries.status.pending"),
        )

        self.mongo = MongoConfiguration(
            url=os.environ.get("SIMOD_MONGO_URL", "mongodb://localhost:27017/"),
            database=os.environ.get("SIMOD_MONGO_DATABASE", "simod"),
            discoveries_collection=os.environ.get("SIMOD_MONGO_COLLECTION", "discoveries"),
        )
