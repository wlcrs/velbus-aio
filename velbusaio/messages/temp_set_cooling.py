"""TempSetCoolingMessage class.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.command_registry import register
from velbusaio.message_fields import ByteField, DeclarativeMessage

COMMAND_CODE = 0xDF


@register(COMMAND_CODE)
class TempSetCoolingMessage(DeclarativeMessage):
    """Temp Set Cooling Message."""

    _command_code = COMMAND_CODE
    _priority = None

    mode = ByteField(0, default=0xAA)
