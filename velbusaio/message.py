"""The Velbus message base class and framing parser."""

from __future__ import annotations

import binascii
import enum
import json
import logging
from typing import Any

from velbusaio.command_registry import commandRegistry
from velbusaio.const import (
    END_BYTE,
    HEADER_LENGTH,
    MAXIMUM_MESSAGE_SIZE,
    MINIMUM_MESSAGE_SIZE,
    NO_RTR,
    PRIORITIES,
    PRIORITY_FIRMWARE,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    RTR,
    START_BYTE,
    TAIL_LENGTH,
)
from velbusaio.util import (
    byte_to_channels as util_byte_to_channels,
    channels_to_byte as util_channels_to_byte,
    checksum as calculate_checksum,
)

logger = logging.getLogger(__name__)


class ParserError(Exception):
    """Error when invalid message is received or parsed."""


class ParseError(ParserError):
    """Exception raised for errors in raw frame parsing."""


class Message:
    """Base Velbus message."""

    def __init__(
        self,
        address: int | None = 0,
        priority: int = PRIORITY_LOW,
        rtr: bool = False,
        data: bytes | bytearray = b"",
    ) -> None:
        """Initialize message with default values."""
        self.priority = priority
        self.address: int = address if address is not None else 0
        self.rtr: bool = rtr
        self._data: Any = bytes(data) if isinstance(data, (bytes, bytearray)) else data
        self.set_defaults(address)

    @property
    def data(self) -> Any:
        """Return raw data bytes/objects if set, or binary payload data."""
        if self._data is not None and self._data != b"":
            return self._data
        try:
            return self.data_to_binary()
        except NotImplementedError:
            return self._data

    @data.setter
    def data(self, value: Any) -> None:
        """Set raw data bytes or payload value."""
        if isinstance(value, (bytes, bytearray)):
            self._data = bytes(value)
        else:
            self._data = value

    @property
    def command(self) -> int | None:
        """Return the command byte of the message."""
        data_bytes = self.data
        if isinstance(data_bytes, (bytes, bytearray)) and len(data_bytes) > 0:
            return data_bytes[0]
        return None

    @property
    def data_only(self) -> bytes | None:
        """Return the data bytes excluding the command byte."""
        data_bytes = self.data
        if isinstance(data_bytes, (bytes, bytearray)) and len(data_bytes) > 1:
            return bytes(data_bytes[1:])
        return None

    def set_attributes(self, priority: int, address: int, rtr: bool) -> None:
        """Set attributes of the message."""
        self.priority = priority
        self.address = address
        self.rtr = rtr

    def populate(self, priority: int, address: int, rtr: bool, data: bytes) -> None:
        """Populate message from raw data."""
        self.priority = priority
        self.address = address
        self.rtr = rtr
        self._data = bytes(data) if data else b""

    def set_defaults(self, address: int | None) -> None:
        """Set defaults.

        If a message has different than low priority or NO_RTR set,
        then this method needs override in subclass
        """
        if address is not None:
            self.set_address(address)
        self.set_low_priority()
        self.set_no_rtr()

    def set_address(self, address: int) -> None:
        """Set the address of the message."""
        self.address = address

    def data_to_binary(self) -> bytes:
        """Convert message data to binary format."""
        if self._data:
            return self._data
        raise NotImplementedError

    def to_bytes(self) -> bytes:
        """Convert the Message to framed wire bytes."""
        payload = self.data_to_binary()
        header_bytes = bytes(
            [
                START_BYTE,
                self.priority,
                self.address,
                (RTR if self.rtr else NO_RTR) | len(payload),
            ]
        )
        tail_bytes = bytes([calculate_checksum(header_bytes + payload), END_BYTE])
        return header_bytes + payload + tail_bytes

    @classmethod
    def parse_frame(
        cls, rawmessage: bytearray, module_type: int | None = None
    ) -> tuple[Message | None, bytearray]:
        """Parse a Message from a bytearray buffer."""
        rawmessage = _trim_buffer_garbage(rawmessage)

        while True:
            if len(rawmessage) < MINIMUM_MESSAGE_SIZE:
                return None, rawmessage

            try:
                msg_info, remaining = _parse_raw_frame(rawmessage)
                if msg_info is None:
                    return None, rawmessage

                priority, address, rtr, payload = msg_info
                command_code = payload[0] if len(payload) > 0 else None

                if command_code is not None and commandRegistry.has_command(
                    command_code, module_type or 0
                ):
                    command_cls = commandRegistry.get_command(
                        command_code, module_type or 0
                    )
                    if command_cls:
                        msg = command_cls()
                        msg.populate(priority, address, rtr, payload[1:])
                        return msg, remaining

                # Return generic Message if no command class registered
                generic_msg = Message(
                    address=address, priority=priority, rtr=rtr, data=payload
                )
                return generic_msg, remaining
            except ParseError:
                logger.exception(
                    "Could not parse the message %s. Truncating invalid data.",
                    binascii.hexlify(rawmessage),
                )
                rawmessage = _trim_buffer_garbage(rawmessage[1:])

    def to_json_basic(self) -> dict[str, Any]:
        """Create JSON structure with generic attributes."""
        me: dict[str, Any] = {}
        me["name"] = str(self.__class__.__name__)
        me.update(self.__dict__.copy())
        for key in list(me.keys()):
            if key == "name":
                continue
            if callable(getattr(self, key)) or key.startswith("__"):
                del me[key]
            elif isinstance(me[key], (bytes, bytearray, enum.Enum)):
                me[key] = str(me[key])
            else:
                try:
                    json.dumps(me[key])
                except (TypeError, ValueError):
                    me[key] = str(me[key])
        return me

    def to_json(self) -> str:
        """Dump object structure to JSON."""
        return json.dumps(self.to_json_basic())

    def __str__(self) -> str:
        """Return string representation of the message."""
        return self.to_json()

    def __repr__(self) -> str:
        """Return string representation of the message."""
        return (
            f"{self.__class__.__name__}(priority={self.priority:02x}, address={self.address:02x},"
            f" rtr={self.rtr!r}, command={self.command},"
            f" data={binascii.hexlify(self.data, ' ')})"
        )

    # Legacy channel helper delegates
    @staticmethod
    def byte_to_channels(byte: int) -> list[int]:
        """Convert a byte to a list of channels."""
        return util_byte_to_channels(byte)

    @staticmethod
    def channels_to_byte(channels: list[int]) -> int:
        """Convert a list of channels to a byte."""
        return util_channels_to_byte(channels)

    def byte_to_channel(self, byte: int) -> int:
        """Convert a byte to a single channel."""
        channels = util_byte_to_channels(byte)
        self.needs_one_channel(channels)
        return channels[0]

    # Legacy validation & setter helper methods
    def parser_error(self, message: str) -> None:
        """Raise a parser error with message."""
        raise ParserError(self.__class__.__name__ + " " + message)

    def needs_rtr(self, rtr: bool) -> None:
        """Check if rtr is set."""
        if not rtr:
            self.parser_error("needs rtr set")

    def set_rtr(self) -> None:
        """Set rtr flag."""
        self.rtr = True

    def needs_no_rtr(self, rtr: bool) -> None:
        """Check if rtr is not set."""
        if rtr:
            self.parser_error("does not need rtr set")

    def set_no_rtr(self) -> None:
        """Unset rtr flag."""
        self.rtr = False

    def needs_low_priority(self, priority: int) -> None:
        """Check if low priority is set."""
        if priority != PRIORITY_LOW:
            self.parser_error("needs low priority set")

    def set_low_priority(self) -> None:
        """Set low priority."""
        self.priority = PRIORITY_LOW

    def needs_high_priority(self, priority: int) -> None:
        """Check if high priority is set."""
        if priority != PRIORITY_HIGH:
            self.parser_error("needs high priority set")

    def set_high_priority(self) -> None:
        """Set high priority."""
        self.priority = PRIORITY_HIGH

    def needs_firmware_priority(self, priority: int) -> None:
        """Check if firmware priority is set."""
        if priority != PRIORITY_FIRMWARE:
            self.parser_error("needs firmware priority set")

    def set_firmware_priority(self) -> None:
        """Set firmware priority."""
        self.priority = PRIORITY_FIRMWARE

    def needs_no_data(self, data: bytes) -> None:
        """Check if no data is included."""
        if not data:
            return
        if len(data) != 0:
            self.parser_error("has data included")

    def needs_data(self, data: bytes, length: int) -> None:
        """Check if data of specific length is included."""
        if len(data) < length:
            self.parser_error(
                "needs " + str(length) + " bytes of data have " + str(len(data))
            )

    def needs_fixed_byte(self, byte: int, value: int) -> None:
        """Check if specific byte has specific value."""
        if byte != value:
            self.parser_error("expects " + chr(value) + " in byte " + chr(byte))

    def needs_one_channel(self, channels: list[int]) -> None:
        """Check if exactly one channel is included."""
        if (
            len(channels) != 1
            or not isinstance(channels[0], int)
            or not channels[0] > 0
            or not channels[0] <= 8
        ):
            self.parser_error("needs exactly one bit set in channel byte")


# Alias RawMessage to Message for full backward compatibility
RawMessage = Message


def _parse_raw_frame(
    rawmessage: bytearray,
) -> tuple[tuple[int, int, bool, bytes] | None, bytearray]:
    """Parse raw frame headers and tail bytes."""
    if len(rawmessage) < MINIMUM_MESSAGE_SIZE or len(rawmessage) > MAXIMUM_MESSAGE_SIZE:
        raise ValueError("Received a raw message with an illegal lemgth")
    if rawmessage[0] != START_BYTE:
        raise ValueError("Received a raw message with the wrong startbyte")

    priority = rawmessage[1]
    if priority not in PRIORITIES:
        raise ParseError(
            f"Invalid priority byte: {priority:02x} in {binascii.hexlify(rawmessage)}"
        )

    address = rawmessage[2]
    rtr = rawmessage[3] & RTR == RTR
    data_size = rawmessage[3] & 0x0F

    if HEADER_LENGTH + data_size + TAIL_LENGTH > len(rawmessage):
        return None, rawmessage

    if rawmessage[HEADER_LENGTH + data_size + 1] != END_BYTE:
        raise ParseError(f"Invalid end byte in {binascii.hexlify(rawmessage)}")

    chk = rawmessage[HEADER_LENGTH + data_size]
    calculated_checksum = calculate_checksum(rawmessage[: HEADER_LENGTH + data_size])

    if calculated_checksum != chk:
        raise ParseError(
            f"Invalid checksum: expected {calculated_checksum:02x},"
            f" but got {chk:02x} in {binascii.hexlify(rawmessage)}"
        )

    data = bytes(rawmessage[HEADER_LENGTH : HEADER_LENGTH + data_size])

    return (
        (priority, address, rtr, data),
        rawmessage[HEADER_LENGTH + data_size + TAIL_LENGTH :],
    )


def _trim_buffer_garbage(rawmessage: bytearray) -> bytearray:
    """Remove leading garbage bytes from a byte stream."""
    if rawmessage and rawmessage[0] != START_BYTE:
        start_index = rawmessage.find(START_BYTE)
        if start_index > -1:
            return rawmessage[start_index:]
        logger.debug(
            "Trimming whole buffer as it does not contain the start byte: %s",
            binascii.hexlify(rawmessage),
        )
        return bytearray()
    return rawmessage
