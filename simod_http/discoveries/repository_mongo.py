import datetime
import os
from pathlib import Path
from typing import Optional, Union, List
from unittest.mock import MagicMock

import pymongo
from bson import ObjectId
from pymongo import MongoClient

from simod_http.discoveries.model import Discovery, DiscoveryStatus
from simod_http.discoveries.repository import DiscoveriesRepositoryInterface


class MongoDiscoveriesRepository(DiscoveriesRepositoryInterface):
    def __init__(self, mongo_client: MongoClient, database: str, collection: str):
        self.mongo_client = mongo_client
        self.database = mongo_client[database]
        self.collection = self.database[collection]
        self._create_indexes()

    def _create_indexes(self):
        self.collection.create_index(
            [
                ("status", pymongo.ASCENDING),
                ("created_timestamp", pymongo.ASCENDING),
            ]
        )

    def create(self, discovery: Discovery, discoveries_storage_path: Path) -> Discovery:
        discovery.created_timestamp = datetime.datetime.now()

        result = self.collection.insert_one(discovery.to_dict())

        discovery.set_id(str(result.inserted_id))

        output_dir = discoveries_storage_path / discovery.get_id()
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery.output_dir = str(output_dir)

        return discovery

    def get(self, discovery_id: str) -> Optional[Discovery]:
        oid = ObjectId(discovery_id)

        result = self.collection.find_one({"_id": oid})

        if result is None:
            return None

        # ObjectId to str
        discovery = Discovery(**result)
        discovery.set_id(str(discovery_id))

        return discovery

    def save(self, discovery: Discovery):
        oid = ObjectId(discovery.get_id())

        self.collection.update_one(
            {"_id": oid},
            {"$set": discovery.to_dict(without_id=True)},
            upsert=True,
        )

    def save_status(self, discovery_id: str, status: DiscoveryStatus, archive_url: Optional[str] = None):
        oid = ObjectId(discovery_id)

        updated_object = {
            "status": status.value,
        }

        if status == DiscoveryStatus.RUNNING:
            updated_object["started_timestamp"] = datetime.datetime.now()
        elif (
            status == DiscoveryStatus.FAILED or status == DiscoveryStatus.DELETED or status == DiscoveryStatus.SUCCEEDED
        ):
            updated_object["finished_timestamp"] = datetime.datetime.now()

        if status == DiscoveryStatus.SUCCEEDED and archive_url is not None:
            updated_object["archive_url"] = archive_url

        self.collection.update_one(
            {"_id": oid},
            {"$set": updated_object},
            upsert=False,
        )

    def delete(self, discovery_id: str):
        oid = ObjectId(discovery_id)

        self.collection.delete_one({"_id": oid})

    def get_all(self) -> List[Discovery]:
        result = self.collection.find({})
        return [Discovery(**r) for r in result]

    def delete_all(self) -> int:
        result = self.collection.delete_many({})
        return result.deleted_count


def make_mongo_discoveries_repository(
    mongo_client: MongoClient,
    database: str,
    collection: str,
) -> Union[MongoDiscoveriesRepository, MagicMock]:
    use_fake = os.environ.get("SIMOD_FAKE_DISCOVERIES_REPOSITORY", "false").lower() == "true"
    if use_fake:
        repository = MagicMock()
        repository.create.return_value = Discovery(configuration_path="fake", status=DiscoveryStatus.PENDING)
        repository.get.return_value = Discovery(configuration_path="fake", status=DiscoveryStatus.PENDING)
        return repository
    else:
        return MongoDiscoveriesRepository(
            mongo_client=mongo_client,
            database=database,
            collection=collection,
        )
