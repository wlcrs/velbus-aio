"""Velbus asyncio network / serial protocol implementation."""

from __future__ import annotations

import asyncio
import binascii
from collections.abc import Callable, Coroutine
import logging
import time
from typing import Any

import backoff

from velbusaio.const import (
    MAXIMUM_MESSAGE_SIZE,
    MINIMUM_MESSAGE_SIZE,
    SLEEP_TIME,
)
from velbusaio.message import Message, ParserError


class VelbusProtocol(asyncio.BufferedProtocol):
    """AsyncIO Protocol for Velbus."""

    def __init__(
        self,
        message_received_callback: Callable[[Message], Coroutine[Any, Any, None]],
        connection_state_callback: (
            Callable[[bool], Coroutine[Any, Any, None]] | None
        ) = None,
    ) -> None:
        """Initialize the VelbusProtocol."""
        self._log = logging.getLogger("velbus-protocol")
        self._message_received_callback = message_received_callback
        self._connection_state_callback = connection_state_callback
        self.transport: asyncio.Transport | None = None
        self._write_transport_lock = asyncio.Lock()
        self._send_queue: asyncio.Queue[Message | None] = asyncio.Queue()
        self._last_activity_time: float = 0.0
        self._closing: bool = False
        self._restart_writer: bool = False
        self._writer_task: asyncio.Future[None] | None = None
        self._serial_buf: bytes = b""
        self._buffer: bytearray = bytearray(MAXIMUM_MESSAGE_SIZE * 2)
        self._buffer_view: memoryview = memoryview(self._buffer)

    def is_connected(self) -> bool:
        """Return True if connection is alive."""
        return (
            self.transport is not None
            and not self.transport.is_closing()
            and not self._closing
        )

    def seconds_since_last_activity(self) -> float:
        """Return number of seconds since any message was sent or received."""
        if self._last_activity_time == 0.0:
            return 0.0
        return time.time() - self._last_activity_time

    def _notify_connection_state_callbacks(self, state: bool) -> None:
        if self._connection_state_callback:
            asyncio.ensure_future(self._connection_state_callback(state))  # noqa: RUF006

    # Everything connection-related

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Called when a Velbus connection is made."""
        self.transport = transport  # type: ignore[assignment]
        self._log.info("Connection established to Velbus")
        self._last_activity_time = time.time()

        self._restart_writer = True
        self.restart_writing()

        # Notify callbacks that connection is established
        self._notify_connection_state_callbacks(True)

    def pause_writing(self) -> None:
        """Pause writing."""
        self._restart_writer = False
        if self._writer_task:
            self._send_queue.put_nowait(None)

    def restart_writing(self) -> None:
        """Resume writing."""
        if self._restart_writer and not self._write_transport_lock.locked():
            self._writer_task = asyncio.ensure_future(
                self._get_message_from_send_queue()
            )
            self._writer_task.add_done_callback(lambda _future: self.restart_writing())

    def close(self) -> None:
        """Close the Velbus connection."""
        self._closing = True
        self._restart_writer = False
        if self.transport:
            self.transport.close()

    def connection_lost(self, exc: Exception | None) -> None:
        """Called when the Velbus connection is lost."""
        self.transport = None
        self.pause_writing()

        if self._closing:
            return  # Connection loss was expected, nothing to do here...
        if exc is None:
            self._log.warning("EOF received from Velbus")
        else:
            self._log.error(f"Velbus connection lost: {exc!r}")

        self._notify_connection_state_callbacks(False)

    # Everything read-related

    def get_buffer(self, sizehint: int) -> memoryview:
        """Provide a writable buffer for the BufferedProtocol read path."""
        return self._buffer_view

    def data_received(self, data: bytes) -> None:
        """Receive data from the Streaming protocol."""
        self._last_activity_time = time.time()
        self._serial_buf += data
        self._log.debug(
            "RX: {nbytes} bytes: {data_hex}".format(
                nbytes=len(data),
                data_hex=binascii.hexlify(self._serial_buf[: len(data)], " "),
            )
        )
        _recheck = True

        while len(self._serial_buf) >= MINIMUM_MESSAGE_SIZE and _recheck:
            head = bytearray(self._serial_buf[:MAXIMUM_MESSAGE_SIZE])
            tail = self._serial_buf[MAXIMUM_MESSAGE_SIZE:]

            msg, remaining_data = Message.parse_frame(head)

            if msg is not None:
                asyncio.ensure_future(self._process_message(msg))  # noqa: RUF006
                _recheck = True
            else:
                _recheck = False
            self._serial_buf = bytes(remaining_data) + tail

    def buffer_updated(self, nbytes: int) -> None:
        """Receive data from the BufferedProtocol read path."""
        self.data_received(bytes(self._buffer_view[:nbytes]))

    async def _process_message(self, msg: Message) -> None:
        try:
            await self._message_received_callback(msg)
        except ParserError as exc:
            self._log.warning(f"Dropping unparsable message ({exc}): {msg}")

    # Everything write-related

    async def write_auth_key(self, authkey: str) -> None:
        """Send authentication key to Velbus interface."""
        self._log.debug("TX: authentication key")
        if self.transport is not None and not self.transport.is_closing():
            self.transport.write(authkey.encode("utf-8"))

    async def send_message(self, msg: Message) -> None:
        """Queue a message to be sent to Velbus."""
        self._send_queue.put_nowait(msg)

    async def _get_message_from_send_queue(self) -> None:
        """Get messages from the send queue and write them to Velbus."""
        self._log.debug("Starting Velbus write message from send queue")
        self._log.debug("Acquiring write lock")
        await self._write_transport_lock.acquire()
        while self._restart_writer:
            # wait for an item from the queue
            msg_info: Message | None = await self._send_queue.get()
            if msg_info is None:
                self._restart_writer = False
                if self._write_transport_lock.locked():
                    self._write_transport_lock.release()
                return
            message_sent = False
            try:
                start_time = time.perf_counter()
                while not message_sent:
                    message_sent = await self._write_message(msg_info)
                send_time = time.perf_counter() - start_time

                self._send_queue.task_done()  # indicate that the item of the queue has been processed

                queue_sleep_time = self._calculate_queue_sleep_time(msg_info, send_time)
                await asyncio.sleep(queue_sleep_time)

            except (asyncio.CancelledError, GeneratorExit) as exc:
                if not self._closing:
                    self._log.error(f"Stopping Velbus writer due to {exc!r}")
                self._restart_writer = False
            except (OSError, RuntimeError) as exc:
                self._log.error(f"Restarting Velbus writer due to {exc!r}")
                self._restart_writer = True
        if self._write_transport_lock.locked():
            self._write_transport_lock.release()
        self._log.debug("Ending Velbus write message from send queue")

    @staticmethod
    def _calculate_queue_sleep_time(msg_info: Message, send_time: float) -> float:
        """Calculate the sleep time needed after sending a message to Velbus."""
        sleep_time = SLEEP_TIME

        if msg_info.rtr:
            sleep_time = SLEEP_TIME

        if msg_info.command == 0xEF:
            sleep_time = SLEEP_TIME * 33

        if send_time > sleep_time:
            return 0.0
        return sleep_time - send_time

    @backoff.on_predicate(
        backoff.expo,
        lambda is_sent: not is_sent,
        max_tries=10,
    )
    async def _write_message(self, msg: Message) -> bool:
        """Write a message to Velbus."""
        self._log.debug(f"TX: {msg}")
        if self.transport and not self.transport.is_closing():
            self.transport.write(msg.to_bytes())
            self._last_activity_time = time.time()
            return True
        return False

    async def wait_on_all_messages_sent_async(self) -> None:
        """Wait until all messages in the send queue are sent."""
        self._log.debug("Waiting on all messages sent")
        await self._send_queue.join()
