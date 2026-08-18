"""TempSensorStatus message implementation.

:author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from velbusaio.message_fields import (
    BitField,
    ByteField,
    DeclarativeMessage,
    HalfDegreeField,
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

    local_control = BitField(0, bit=0)
    status_mode = BitField(0, bit_range=(1, 2), json_map=STATUS_MAP)
    auto_send = BitField(0, bit=3)
    mode = BitField(0, bit_range=(4, 6), json_map=MODE_MAP)
    cool_mode = BitField(0, bit=7)
    reserved = ByteField(1)

    heater = BitField(2, bit=0)
    boost = BitField(2, bit=1)
    pump = BitField(2, bit=2)
    cooler = BitField(2, bit=3)
    alarm1 = BitField(2, bit=4)
    alarm2 = BitField(2, bit=5)
    alarm3 = BitField(2, bit=6)
    alarm4 = BitField(2, bit=7)

    current_temp = HalfDegreeField(3)
    target_temp = HalfDegreeField(4)
    sleep_timer = Int16Field(5)

    def getCurTemp(self) -> float | None:
        """Get current temperature."""
        return self.current_temp
