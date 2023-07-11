import json
import logging
import time
from typing import Union

import pika
import pika.exceptions
from pika.spec import PERSISTENT_DELIVERY_MODE

from simod_http.discoveries.model import Discovery
from simod_http.exceptions import InternalServerError


class BrokerClient:
    def __init__(
        self,
        broker_url: str,
        exchange_name: str,
        routing_key: str,
        connection: Union[pika.BlockingConnection, None] = None,
        channel: Union[pika.adapters.blocking_connection.BlockingChannel, None] = None,
    ):
        self._broker_url = broker_url
        self._exchange_name = exchange_name
        self._routing_key = routing_key

        self._connection = connection
        self._channel = channel

        self._retries = 5
        self._retry_delay = 1

    def __repr__(self):
        return (
            f"BrokerClient(_broker_url={self._broker_url}, "
            f"_exchange_name={self._exchange_name}, "
            f"_routing_key={self._routing_key})"
        )

    def connect(self):
        logging.info(f"Connecting to the broker at {self._broker_url}")
        parameters = pika.URLParameters(self._broker_url)

        try:
            self._connection = pika.BlockingConnection(parameters)
            self._channel = self._connection.channel()
            self._channel.exchange_declare(exchange=self._exchange_name, exchange_type="topic", durable=True)

        except pika.exceptions.AMQPConnectionError:
            logging.warning(f"Failed to connect to the broker at {self._broker_url}. Retrying...")
            self._retries -= 1
            if self._retries > 0:
                time.sleep(self._retry_delay)
                self.connect()
            else:
                raise RuntimeError(f"Failed to connect to the broker at {self._broker_url}")

        self._retries = 5

    def publish_discovery(self, discovery: Discovery):
        if self._broker_url is None:
            logging.error("Broker client is not initialized")
            raise InternalServerError(message="Broker client is not initialized")

        self.basic_publish_discovery(discovery)

    def basic_publish_discovery(self, discovery: Discovery):
        parameters = pika.URLParameters(self._broker_url)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.exchange_declare(exchange=self._exchange_name, exchange_type="topic", durable=True)

        discovery_id = discovery.get_id()

        body = json.dumps(
            {
                "discovery_id": discovery_id,
                "configuration_path": discovery.configuration_path,
            }
        )

        channel.basic_publish(
            exchange=self._exchange_name,
            routing_key=self._routing_key,
            body=body.encode(),
            properties=pika.BasicProperties(
                delivery_mode=PERSISTENT_DELIVERY_MODE,
                content_type="application/json",
            ),
        )
        connection.close()
        logging.info(f"Published discovery {discovery_id} to {self._routing_key}")

    def close(self):
        if self._connection is not None and self._channel is not None:
            self._channel.close()
            self._connection.close()


def make_broker_client(broker_url: str, exchange_name: str, routing_key: str) -> BrokerClient:
    return BrokerClient(
        broker_url=broker_url,
        exchange_name=exchange_name,
        routing_key=routing_key,
    )
