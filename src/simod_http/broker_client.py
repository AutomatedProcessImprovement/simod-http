import logging
import time
from typing import Union

import pika
import pika.exceptions
from pika.spec import PERSISTENT_DELIVERY_MODE


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

    def connect(self):
        logging.info(f'Connecting to the broker at {self._broker_url}')
        parameters = pika.URLParameters(self._broker_url)

        try:
            self._connection = pika.BlockingConnection(parameters)
            self._channel = self._connection.channel()
            self._channel.exchange_declare(exchange=self._exchange_name, exchange_type='topic', durable=True)

        except pika.exceptions.AMQPConnectionError:
            logging.warning(f'Failed to connect to the broker at {self._broker_url}. Retrying...')
            self._retries -= 1
            if self._retries > 0:
                time.sleep(self._retry_delay)
                self.connect()
            else:
                raise RuntimeError(f'Failed to connect to the broker at {self._broker_url}')

        self._retries = 5

    def publish_request(self, request_id: str):
        if self._connection is None or self._channel is None or self._connection.is_closed or self._channel.is_closed:
            self.connect()

        try:
            self._channel.basic_publish(
                exchange=self._exchange_name,
                routing_key=self._routing_key,
                body=request_id.encode(),
                properties=pika.BasicProperties(
                    delivery_mode=PERSISTENT_DELIVERY_MODE,
                ),
            )

            logging.info(f'Published request {request_id} to {self._routing_key}')

        except pika.exceptions.ConnectionClosed:
            logging.warning(f'Failed to publish request {request_id} to {self._routing_key} '
                            f'because the connection is closed. Reconnecting...')
            self.connect()
            self.publish_request(request_id)

        except pika.exceptions.ChannelClosed:
            logging.warning(f'Failed to publish request {request_id} to {self._routing_key} '
                            f'because the channel is closed. Reconnecting...')
            self.connect()
            self.publish_request(request_id)

        except pika.exceptions.StreamLostError:
            logging.warning(f'Failed to publish request {request_id} to {self._routing_key} '
                            f'because the stream is lost. Reconnecting...')
            self.connect()
            self.publish_request(request_id)
