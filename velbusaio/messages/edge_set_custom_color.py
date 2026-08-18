"""Edge Set Custom Color message class.

:author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from velbusaio.message_fields import BitField, ByteField, DeclarativeMessage

COMMAND_CODE = 0xD4


class EdgeSetCustomColor(DeclarativeMessage):
    """Edge Set Custom Color message."""

    _command_code = COMMAND_CODE
    _priority = None

    pallet = ByteField(0, default=31)
    rgb = BitField(1, bit=7)
    saturation = BitField(1, bit_range=(0, 6))
    red = ByteField(2)
    green = ByteField(3)
    blue = ByteField(4)
