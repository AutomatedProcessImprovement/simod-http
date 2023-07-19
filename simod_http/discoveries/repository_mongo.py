import datetime
import os
from pathlib import Path
from typing import List, Optional, Union
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

        result = self.collection.insert_one(discovery.to_mongo_dict())

        discovery.set_id(str(result.inserted_id))

        output_dir = discoveries_storage_path / discovery.id
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery.output_dir = str(output_dir)

        return discovery

    def get(self, discovery_id: str) -> Optional[Discovery]:
        oid = ObjectId(discovery_id)

        result = self.collection.find_one({"_id": oid})

        if result is None:
            return None

        return Discovery(**result)

    def save(self, discovery: Discovery):
        oid = ObjectId(discovery.id)

        self.collection.update_one(
            {"_id": oid},
            {"$set": discovery.to_mongo_dict(without_id=True)},
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
    database: str = os.environ.get("SIMOD_MONGO_DATABASE", "simod"),
    collection: str = os.environ.get("SIMOD_MONGO_COLLECTION", "discoveries"),
) -> Union[MongoDiscoveriesRepository, MagicMock]:
    return MongoDiscoveriesRepository(
        mongo_client=mongo_client,
        database=database,
        collection=collection,
    )


def make_mongo_client(mongo_url: str = os.environ.get("SIMOD_MONGO_URL", "mongodb://localhost:27017/")) -> MongoClient:
    return MongoClient(mongo_url, username="root", password="example")
