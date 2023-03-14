import logging

import pika
from pika.spec import PERSISTENT_DELIVERY_MODE


class BrokerClient:
    def __init__(self, broker_url: str, exchange_name: str, pending_routing_key: str):
        self._broker_url = broker_url
        self._exchange_name = exchange_name
        self._pending_routing_key = pending_routing_key

        self._stopping = False
        self._is_ready = False
        self._queue_name = ''

        logging.info(f'Connecting to {self._broker_url}')
        params = pika.URLParameters(self._broker_url)
        self._connection = pika.SelectConnection(
            params,
            on_open_callback=self._on_connection_open,
            on_open_error_callback=self._on_connection_open_error,
            on_close_callback=self._on_connection_closed,
        )
        self._connection.ioloop.start()

    def _on_connection_open(self, _connection):
        self._channel = self._connection.channel(on_open_callback=self._on_channel_open)

    def _on_connection_open_error(self, _connection, err):
        logging.error(f'Connection open failed: {err}. Retrying...')
        self._connection.ioloop.call_later(5, self._connection.ioloop.stop)

    def _on_connection_closed(self, _connection, reason):
        self._channel = None

        if self._stopping:
            self._connection.ioloop.stop()
        else:
            logging.warning(f'Connection closed, reopening in 5 seconds: {reason}')
            self._connection.ioloop.call_later(5, self._connection.ioloop.stop)

    def _on_channel_open(self, channel):
        self._channel = channel

        self._channel.add_on_close_callback(self._on_channel_closed)

        self._channel.exchange_declare(
            exchange=self._exchange_name,
            exchange_type='topic',
            durable=True,
            callback=self._on_exchange_declared,
        )

    def _on_channel_closed(self, channel, reason):
        logging.warning(f'Channel {channel} was closed: {reason}')

        self._channel = None

        if not self._stopping:
            self._connection.close()

    def _on_exchange_declared(self, _frame, _userdata):
        self._channel.queue_declare(queue=self._queue_name, exclusive=True, callback=self._on_queue_declared)

    def _on_queue_declared(self, frame, _userdata):
        self._channel.queue_bind(
            queue=frame.method.queue,
            exchange=self._exchange_name,
            routing_key=self._pending_routing_key,
        )

        self._is_ready = True

    def publish_request(self, request_id: str):
        if not self._is_ready:
            logging.warning(f'Cannot publish request {request_id} because the client is not ready')
            return

        self._channel.basic_publish(
            exchange=self._exchange_name,
            routing_key=self._pending_routing_key,
            body=request_id.encode(),
            properties=pika.BasicProperties(
                delivery_mode=PERSISTENT_DELIVERY_MODE,
            ),
        )

        logging.info(f'Published request {request_id} to {self._pending_routing_key}')

    def stop(self):
        logging.info('Stopping the broker client')

        self._stopping = True

        if self._channel is not None:
            self._channel.close()

        if self._connection is not None:
            self._connection.close()
