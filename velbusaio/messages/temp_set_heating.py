"""Temp Set Heating Message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.message_fields import ByteField, DeclarativeMessage

COMMAND_CODE = 0xE0


class TempSetHeatingMessage(DeclarativeMessage):
    """Set Heating Temperature Message."""

    _command_code = COMMAND_CODE
    _priority = None

    mode = ByteField(0, default=0xAA)
