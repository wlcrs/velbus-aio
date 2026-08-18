"""Counter Value message.

:author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from velbusaio.message_fields import (
    BitField,
    ChannelField,
    DeclarativeMessage,
    Int24Field,
    Int32Field,
)


COMMAND_CODE = 0xA4


class CounterValueMessage(DeclarativeMessage):
    """Counter Value message.

    Manual VMB8IN-20:
    DATABYTE2 bits 7-4 = Counter channel 1 to 8 (0-7)
    DATABYTE2 bits 3-0 = Highest nibble (bits 19...16) of Power
    DATABYTE3 = high byte of power
    DATABYTE4 = low byte of power
    DATABYTE5 = MSB of energy counter
    DATABYTE6 = upper byte of energy counter
    DATABYTE7 = high byte of energy counter
    DATABYTE8 = LSB of energy counter
    """

    _command_code = COMMAND_CODE
    _priority = None
    _data_length = 7
    _generates_data_to_binary = False

    channel = BitField(0, bit_range=(4, 7), offset=1)
    power = Int24Field(0, bit_range=(0, 19))
    energy = Int32Field(3)



    def get_channels(self):
        """:return: list"""
        return self.channel
