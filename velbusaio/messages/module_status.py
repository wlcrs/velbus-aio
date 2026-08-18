"""Module Status Request Message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.message_fields import (
    BitField,
    ByteField,
    ChannelsField,
    DeclarativeMessage,
    Int16Field,
)

COMMAND_CODE = 0xED

PROGRAM_SELECTION = {0: "none", 1: "summer", 2: "winter", 3: "holiday"}


class ModuleStatusMessage(DeclarativeMessage):
    """Module Status Message."""

    _command_code = COMMAND_CODE
    _data_length = 4

    closed = ChannelsField(0)
    led_on = ChannelsField(1)
    led_slow_blinking = ChannelsField(2)
    led_fast_blinking = ChannelsField(3)


class ModuleStatusMessage2(DeclarativeMessage):
    """Module Status Message for specific modules."""

    _command_code = COMMAND_CODE
    _data_length = 6

    closed = ChannelsField(0)
    enabled = ChannelsField(1)
    normal = ChannelsField(2)
    locked = ChannelsField(3)
    programenabled = ChannelsField(4)
    selected_program = BitField(
        5, bit_range=(0, 1), json_map=PROGRAM_SELECTION, serializable=True
    )


class ModuleStatusPirMessage(DeclarativeMessage):
    """Module Status PIR Message."""

    _command_code = COMMAND_CODE
    _data_length = 7
    _generates_data_to_binary = False

    dark = BitField(0, bit=0)  # data[0] bit 1
    light = BitField(0, bit=1)  # data[0] bit 2
    motion1 = BitField(0, bit=2)  # data[0] bit 3
    light_motion1 = BitField(0, bit=3)  # data[0] bit 4
    motion2 = BitField(0, bit=4)  # data[0] bit 5
    light_motion2 = BitField(0, bit=5)  # data[0] bit 6
    low_temp_alarm = BitField(0, bit=6)  # data[0] bit 7
    high_temp_alarm = BitField(0, bit=7)  # data[0] bit 8
    light_value = Int16Field(1)  # data[1] and data[2]
    selected_program = BitField(5, bit_range=(0, 1), json_map=PROGRAM_SELECTION)


class ModuleStatusGP4PirMessage(DeclarativeMessage):
    """Module Status GP4 PIR Message."""

    _command_code = COMMAND_CODE
    _data_length = 7

    closed = ChannelsField(0)
    enabled_mask = BitField(1, bit_range=(0, 3))
    light_value_hi = BitField(1, bit_range=(4, 5))
    light_value_lo = ByteField(2)
    locked = ChannelsField(3)
    programenabled = ChannelsField(4)
    selected_program = BitField(5, bit_range=(0, 1), json_map=PROGRAM_SELECTION)
    light_value_send_interval = ByteField(6)

    @property
    def enabled(self) -> list[int]:
        """Return list of enabled channels (1..4)."""
        return [offset + 1 for offset in range(4) if self.enabled_mask & (1 << offset)]

    @enabled.setter
    def enabled(self, channels: list[int]) -> None:
        val = 0
        for ch in channels:
            if 1 <= ch <= 4:
                val |= 1 << (ch - 1)
        self.enabled_mask = val

    @property
    def light_value(self) -> int:
        """Return 10-bit light value."""
        return (self.light_value_hi << 8) | self.light_value_lo

    @light_value.setter
    def light_value(self, value: int) -> None:
        self.light_value_hi = (value >> 8) & 0x03
        self.light_value_lo = value & 0xFF
