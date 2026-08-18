"""Receive Ready Message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.message_fields import DeclarativeMessage

COMMAND_CODE = 0x0C


class ReceiveReadyMessage(DeclarativeMessage):
    """Receive Ready Message."""

    _command_code = COMMAND_CODE
    _priority = None
    _data_length = 0
