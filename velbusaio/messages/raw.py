"""Raw Messages.

:author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from velbusaio.command_registry import register
from velbusaio.const import PRIORITY_LOW, MessagePriority
from velbusaio.message import Message
from velbusaio.message_fields import DeclarativeMessage

COMMAND_CODE = 0xAF


@register(COMMAND_CODE)
class MeteoRawMessage(Message):
    """Meteo Raw Message."""

    def __init__(
        self,
        address: int = 0,
        rain: float = 0,
        light: float = 0,
        wind: float = 0,
    ) -> None:
        """Initialize Meteo Raw Message Object."""
        Message.__init__(self, address=address)
        self.rain: float = rain
        self.light: float = light
        self.wind: float = wind

    @classmethod
    def from_bytes(
        cls,
        data: bytes | bytearray,
        address: int = 0,
        priority: int = PRIORITY_LOW,
        rtr: bool = False,
    ) -> MeteoRawMessage:
        """Parse MeteoRawMessage from raw payload bytes."""
        data_bytes = bytes(data)
        msg = cls(address=address)
        msg.needs_no_rtr(rtr)
        msg.needs_data(data_bytes, 6)
        msg.priority = (
            MessagePriority(priority)
            if isinstance(priority, int)
            and priority in MessagePriority._value2member_map_
            else priority
        )  # type: ignore[assignment]
        msg.rtr = rtr
        msg.rain = (((data_bytes[0] << 8) | data_bytes[1]) / 32) * 0.1
        msg.light = ((data_bytes[2] << 8) | data_bytes[3]) / 32
        msg.wind = (((data_bytes[4] << 8) | data_bytes[5]) / 32) * 0.1
        return msg


@register(COMMAND_CODE)
class SensorRawMessage(DeclarativeMessage):
    """Sensor Raw Message."""

    _command_code = COMMAND_CODE
    _priority = None
    _data_length = 5
    _generates_data_to_binary = False

    def __init__(
        self,
        address: int = 0,
        sensor: int = 0,
        mode: int = 0,
        value: float = 0,
        unit: str | None = None,
    ) -> None:
        """Initialize Sensor Raw Message Object."""
        Message.__init__(self, address=address)
        self.sensor = sensor
        self.mode = mode
        self.value = value
        self.unit = unit

    @classmethod
    def from_bytes(
        cls,
        data: bytes | bytearray,
        address: int = 0,
        priority: int = PRIORITY_LOW,
        rtr: bool = False,
    ) -> SensorRawMessage:
        """Parse SensorRawMessage from raw payload bytes."""
        data_bytes = bytes(data)
        msg = cls(address=address)
        msg.needs_no_rtr(rtr)
        msg.needs_data(data_bytes, 5)
        msg.priority = (
            MessagePriority(priority)
            if isinstance(priority, int)
            and priority in MessagePriority._value2member_map_
            else priority
        )  # type: ignore[assignment]
        msg.rtr = rtr
        msg.sensor = data_bytes[0]
        msg.mode = data_bytes[1]
        msg.value = (data_bytes[2] << 16) | (data_bytes[3] << 8) | data_bytes[4]
        if msg.mode == 0:
            msg.value = msg.value * 0.25
            msg.unit = "mV"
        elif msg.mode == 1:
            msg.value = msg.value * 5
            msg.unit = "µA"
        elif msg.mode == 2:
            msg.value = msg.value * 0.25
            msg.unit = "ohm"
        elif msg.mode == 3:
            msg.value = msg.value * 0.5
            msg.unit = "µS"
        return msg
