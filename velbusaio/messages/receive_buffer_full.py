"""Receive Buffer Full Message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.const import MessagePriority
from velbusaio.message_fields import DeclarativeMessage

COMMAND_CODE = 0x0B


class ReceiveBufferFullMessage(DeclarativeMessage):
    """Receive Buffer Full Message."""

    _command_code = COMMAND_CODE
    _priority = MessagePriority.HIGH
    _data_length = 0
