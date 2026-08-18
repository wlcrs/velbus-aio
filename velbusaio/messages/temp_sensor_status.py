"""TempSensorStatus message implementation.

:author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from velbusaio.message_fields import (
    BitField,
    ComputedField,
    DeclarativeMessage,
    Field,
    Int16Field,
)

COMMAND_CODE = 0xEA
STATUS_MAP = {0: "run", 1: "manual", 2: "sleep", 3: "disable"}
MODE_MAP = {0: "safe", 1: "night", 2: "day", 4: "comfort"}


class TempSensorStatusMessage(DeclarativeMessage):
    """TempSensorStatus message class."""

    _command_code = COMMAND_CODE
    _priority = None
    _data_length = 7
    _generates_data_to_binary = False

    local_control = BitField(0, bit=0, default=0, serializable=False)
    status_mode = BitField(
        0,
        bit_range=(1, 2),
        default=0,
        json_map=STATUS_MAP,
        serializable=False,
    )
    auto_send = BitField(0, bit=3, default=0, serializable=False)
    mode = BitField(
        0,
        bit_range=(4, 6),
        default=0,
        json_map=MODE_MAP,
        serializable=False,
    )
    cool_mode = BitField(0, bit=7, default=False, serializable=False)




    heater = BitField(2, bit=0, default=False, serializable=False)
    boost = BitField(2, bit=1, default=False, serializable=False)
    pump = BitField(2, bit=2, default=False, serializable=False)
    cooler = BitField(2, bit=3, default=False, serializable=False)
    alarm1 = BitField(2, bit=4, default=False, serializable=False)
    alarm2 = BitField(2, bit=5, default=False, serializable=False)
    alarm3 = BitField(2, bit=6, default=False, serializable=False)
    alarm4 = BitField(2, bit=7, default=False, serializable=False)

    current_temp = Field(
        byte_index=3,
        default=None,
        parser=lambda data: (data[3] - 256 if data[3] & 0x80 else data[3]) / 2,
        serializable=False,
    )
    target_temp = Field(
        byte_index=4,
        default=None,
        parser=lambda data: (data[4] - 256 if data[4] & 0x80 else data[4]) / 2,
        serializable=False,
    )
    sleep_timer = Int16Field(5, default=None, serializable=False)

    def getCurTemp(self) -> float | None:
        """Get current temperature."""
        return self.current_temp
