"""Constant for velbusaio.

Author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Final


class BlindState(IntEnum):
    """Blind movement state."""

    STOPPED = 0x00
    OPENING = 0x01
    CLOSING = 0x02


class ButtonLedState(StrEnum):
    """Button LED state with associated command code."""

    command_code: int

    def __new__(cls, value: str, command_code: int) -> ButtonLedState:
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.command_code = command_code
        return obj

    OFF = ("off", 0xF5)
    ON = ("on", 0xF6)
    SLOW = ("slow", 0xF7)
    FAST = ("fast", 0xF8)


class MessagePriority(IntEnum):
    """Velbus message priorities."""

    HIGH = 0xF8
    FIRMWARE = 0xF9
    THIRDPARTY = 0xFA
    LOW = 0xFB
    WEIRD = 0xFC


PRIORITY_HIGH: Final = MessagePriority.HIGH
PRIORITY_FIRMWARE: Final = MessagePriority.FIRMWARE
PRIORITY_LOW: Final = MessagePriority.LOW
PRIORITY_THIRDPARTY: Final = MessagePriority.THIRDPARTY
PRIORITY_WEIRD: Final = MessagePriority.WEIRD

PRIORITIES: Final = [
    MessagePriority.FIRMWARE,
    MessagePriority.HIGH,
    MessagePriority.LOW,
    MessagePriority.THIRDPARTY,
    MessagePriority.WEIRD,
]


HEADER_LENGTH: Final = 4  # Header: [Start Byte, priority, address, RTR+data length]
TAIL_LENGTH: Final = 2  # Tail: [CRC, End Byte]
MAX_BODY_SIZE: Final = 8  # Maximum amount of data bytes in a packet

MINIMUM_MESSAGE_SIZE: Final = (
    HEADER_LENGTH + TAIL_LENGTH
)  # Smallest possible packet: [Start Byte, priority, address, RTR+data length, CRC, End Byte]
MAXIMUM_MESSAGE_SIZE: Final = MINIMUM_MESSAGE_SIZE + MAX_BODY_SIZE

START_BYTE: Final = 0x0F
END_BYTE: Final = 0x04


LENGTH_MASK: Final = 0x0F

RTR: Final = 0x40
NO_RTR: Final = 0x00

CACHEDIR: Final = ".velbuscache"

# Module scan timeout values (in mSec)
SCAN_MODULETYPE_TIMEOUT: Final = 3000  # time to wait for ModuleTypeRequest
SCAN_MODULEINFO_TIMEOUT_INITIAL: Final = 1000  # time to wait for first info (status)
SCAN_MODULEINFO_TIMEOUT_INTERVAL: Final = (
    150  # time to wait for info interval (between next message)
)

DEVICE_CLASS_TEMPERATURE: Final = "temperature"
TEMP_CELSIUS: Final = "°C"
ENERGY_KILO_WATT_HOUR: Final = "kWh"
ENERGY_WATT_HOUR: Final = "Wh"
VOLUME_CUBIC_METER: Final = "m³"  # Not an official constant at HA yet
VOLUME_CUBIC_METER_HOUR: Final = "m³/h"  # Not an official constant at HA yet
VOLUME_LITERS: Final = "L"
VOLUME_LITERS_HOUR: Final = "L/h"  # Not an official constant at HA yet

SLEEP_TIME = 60 / 1000
