"""Counter Status message.

:author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from velbusaio.message_fields import (
    BitField,
    DeclarativeMessage,
    Int16Field,
    Int32Field,
)

COMMAND_CODE = 0xBE


class CounterStatusMessage(DeclarativeMessage):
    """Counter Status message.

    -DB1    last 2 bits   = channel
    -DB1    first 6 bits  = pulses
    -DB2-5                = pulse counter
    -DB6-7                = ms/pulse
    """

    _command_code = COMMAND_CODE
    _priority = None
    _data_length = 7
    _generates_data_to_binary = False

    channel = BitField(0, bit_range=(0, 1), offset=1)
    pulse_units = BitField(0, bit_range=(2, 7))
    counter = Int32Field(1)
    delay = Int16Field(5)

    @property
    def pulses(self) -> int:
        """Return total pulse count per unit."""
        return self.pulse_units * 100

    @property
    def kwh(self) -> float:
        """Return energy in kWh."""
        if not self.pulses:
            return 0.0
        return float(self.counter / self.pulses)

    @property
    def watt(self) -> float:
        """Return power in Watts."""
        if not self.pulses or not self.delay:
            return 0.0
        val = float((1000 * 1000 * 3600) / (self.delay * self.pulses))
        return val if val >= 55 else 0.0

    def get_channels(self):
        """:return: list"""
        return self.channel
