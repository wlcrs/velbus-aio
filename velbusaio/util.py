"""Some common utils."""

from velbusaio.const import MAXIMUM_MESSAGE_SIZE, MINIMUM_MESSAGE_SIZE


# Copyright (c) 2017 Thomas Delaet
# Copied from python-velbus (https://github.com/thomasdelaet/python-velbus)
def checksum(data: bytes | bytearray) -> int:
    """Calculate the checksum of a Velbus message."""
    if len(data) < MINIMUM_MESSAGE_SIZE - 2:
        raise ValueError("The message is shorter then expected")
    if len(data) > MAXIMUM_MESSAGE_SIZE - 2:
        raise ValueError("The message is longer then expected")
    __checksum = 0
    for data_byte in data:
        __checksum += data_byte
    __checksum = -(__checksum % 256) + 256
    return __checksum % 256


class VelbusException(Exception):
    """Velbus Exception."""

    def __init__(self, value):
        """Initialize Velbus Exception with a value."""
        Exception.__init__(self)
        self.value = value

    def __str__(self) -> str:
        """Return string representation of the exception."""
        return repr(self.value)


class MessageParseException(Exception):
    """Message Parse Exception."""


class BitSet:
    """BitSet helper class."""

    def __init__(self, value: int):
        """Initialize BitSet with an integer value."""
        self._value = value

    def __getitem__(self, idx: int) -> bool:
        """Get the boolean value of the bit at the given index."""
        if idx > 8 or idx <= 0:
            raise ValueError("The bitSet id is not within expected range 0 < id < 8")
        return bool((1 << idx) & self._value)

    def __setitem__(self, idx: int, value: bool) -> None:
        """Set the bit at the given index to the boolean value."""
        if idx > 8 or idx <= 0:
            raise ValueError("The bitSet id is not within expected range 0 < id < 8")
        mask = (0xFF ^ (1 << idx)) & self._value
        self._value = mask & (value << idx)

    def __len__(self) -> int:
        """Return the length of the BitSet (always 8)."""
        return 8  # a bitset represents one byte


def byte_to_channels(byte: int) -> list[int]:
    """Convert a byte to a list of channel numbers (1-8)."""
    return [offset + 1 for offset in range(8) if byte & (1 << offset)]


def channels_to_byte(channels: list[int]) -> int:
    """Convert a list of channel numbers (1-8) to a bitmask byte."""
    result = 0
    for offset in range(8):
        if offset + 1 in channels:
            result += 1 << offset
    return result


def byte_to_channel(byte: int) -> int:
    """Convert a byte to a single channel number (1-8)."""
    channels = byte_to_channels(byte)
    if len(channels) != 1:
        raise ValueError(
            f"Expected exactly one bit set in channel byte, got {len(channels)}"
        )
    return channels[0]
