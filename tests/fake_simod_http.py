from unittest.mock import MagicMock

import uvicorn
from pika import BlockingConnection

from simod_http.broker_client import BrokerClient
from simod_http.main import api, logging_config


def stub_broker_client() -> BrokerClient:
    channel = MagicMock()
    connection = MagicMock(spec=BlockingConnection)
    connection.channel.return_value = channel
    client = BrokerClient('', '', '', connection=connection)
    client.publish_request = MagicMock()
    client.connect = MagicMock()
    return client


api.state.app.broker_client = stub_broker_client()

uvicorn.run(
    api,
    host='localhost',
    port=8000,
    log_level='info',
    workers=1,
    log_config=logging_config,
)
