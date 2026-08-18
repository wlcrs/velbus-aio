"""Set Temperature Message.

:author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from velbusaio.message_fields import ByteField, DeclarativeMessage, HalfDegreeField

COMMAND_CODE = 0xE4


class SetTemperatureMessage(DeclarativeMessage):
    """Set Temperature Message.

    The temperature is expressed in degrees Celsius. On the wire DATABYTE3
    holds the value in two's complement with a resolution of 0.5 degrees.
    """

    _command_code = COMMAND_CODE
    _data_length = 2

    temp_type = ByteField(0)
    temp = HalfDegreeField(1)
