import datetime
import os
from pathlib import Path
from typing import Optional, Union, List
from unittest.mock import MagicMock

import pymongo
from bson import ObjectId
from pymongo import MongoClient

from simod_http.requests import JobRequest, RequestStatus
from simod_http.requests_repository import JobRequestsRepositoryInterface


class MongoJobRequestsRepository(JobRequestsRepositoryInterface):
    def __init__(self, mongo_client: MongoClient, database: str, collection: str):
        self.mongo_client = mongo_client
        self.database = mongo_client[database]
        self.collection = self.database[collection]
        self._create_indexes()

    def _create_indexes(self):
        self.collection.create_index([
            ('status', pymongo.ASCENDING),
            ('created_timestamp', pymongo.ASCENDING),
        ])

    def create(self, request: JobRequest, requests_storage_path: Path) -> JobRequest:
        request.created_timestamp = datetime.datetime.now()

        result = self.collection.insert_one(request.to_dict())

        request.set_id(str(result.inserted_id))

        output_dir = requests_storage_path / request.get_id()
        output_dir.mkdir(parents=True, exist_ok=True)
        request.output_dir = str(output_dir)

        return request

    def get(self, request_id: str) -> Optional[JobRequest]:
        oid = ObjectId(request_id)

        result = self.collection.find_one({'_id': oid})

        if result is None:
            return None

        # ObjectId to str
        request = JobRequest(**result)
        request.set_id(str(request_id))

        return request

    def save(self, request: JobRequest):
        oid = ObjectId(request.get_id())

        self.collection.update_one(
            {'_id': oid},
            {'$set': request.to_dict(without_id=True)},
            upsert=True,
        )

    def save_status(self, request_id: str, status: RequestStatus, archive_url: Optional[str] = None):
        oid = ObjectId(request_id)

        updated_object = {
            'status': status.value,
        }

        if status == RequestStatus.RUNNING:
            updated_object['started_timestamp'] = datetime.datetime.now()
        elif status == RequestStatus.FAILED or status == RequestStatus.DELETED or status == RequestStatus.SUCCEEDED:
            updated_object['finished_timestamp'] = datetime.datetime.now()

        if status == RequestStatus.SUCCEEDED and archive_url is not None:
            updated_object['archive_url'] = archive_url

        self.collection.update_one(
            {'_id': oid},
            {'$set': updated_object},
            upsert=False,
        )

    def delete(self, request_id: str):
        oid = ObjectId(request_id)

        self.collection.delete_one({'_id': oid})

    def get_all(self) -> List[JobRequest]:
        result = self.collection.find({})
        return [JobRequest(**r) for r in result]

    def delete_all(self) -> int:
        result = self.collection.delete_many({})
        return result.deleted_count


def make_mongo_job_requests_repository(
        mongo_client: MongoClient,
        database: str,
        collection: str,
) -> Union[MongoJobRequestsRepository, MagicMock]:
    use_fake = os.environ.get('SIMOD_FAKE_REQUESTS_REPOSITORY', 'false').lower() == 'true'
    if use_fake:
        repository = MagicMock()
        repository.create.return_value = JobRequest(configuration_path='fake', status=RequestStatus.PENDING)
        repository.get.return_value = JobRequest(configuration_path='fake', status=RequestStatus.PENDING)
        return repository
    else:
        return MongoJobRequestsRepository(
            mongo_client=mongo_client,
            database=database,
            collection=collection,
        )
