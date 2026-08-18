"""PSU Values Message.

:author: Maikel Punie
"""

from __future__ import annotations

from velbusaio.message_fields import (
    BitField,
    DeclarativeMessage,
    Int16Field,
    Int24Field,
)

COMMAND_CODE = 0xA3


class PsuValuesMessage(DeclarativeMessage):
    """PSU Values Message."""

    _command_code = COMMAND_CODE
    _data_length = 7

    channel = BitField(0, bit_range=(4, 7))
    raw_watt_hi = BitField(0, bit_range=(0, 3))
    raw_watt_lo = Int16Field(1)
    raw_volt = Int16Field(3)
    raw_amp = Int16Field(5)

    @property
    def raw_watt(self) -> int:
        """Return raw 20-bit wattage value."""
        return (self.raw_watt_hi << 16) | self.raw_watt_lo

    @raw_watt.setter
    def raw_watt(self, value: int) -> None:
        self.raw_watt_hi = (value >> 16) & 0x0F
        self.raw_watt_lo = value & 0xFFFF

    @property
    def watt(self) -> float:
        """Return wattage in Watts."""
        return self.raw_watt / 1000

    @watt.setter
    def watt(self, value: float) -> None:
        self.raw_watt = int(round(value * 1000))

    @property
    def volt(self) -> float:
        """Return voltage in Volts."""
        return self.raw_volt / 1000

    @volt.setter
    def volt(self, value: float) -> None:
        self.raw_volt = int(round(value * 1000))

    @property
    def amp(self) -> float:
        """Return current in Amperes."""
        return self.raw_amp / 1000

    @amp.setter
    def amp(self, value: float) -> None:
        self.raw_amp = int(round(value * 1000))


