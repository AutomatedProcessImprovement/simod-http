from unittest.mock import MagicMock

from pika import BlockingConnection

from simod_http.broker_client import BrokerClient


def stub_broker_client() -> BrokerClient:
    channel = MagicMock()
    connection = MagicMock(spec=BlockingConnection)
    connection.channel.return_value = channel
    client = BrokerClient("", "", "", connection=connection)
    client.publish_request = MagicMock()
    client.connect = MagicMock()
    return client
