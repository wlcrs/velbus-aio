"""Cancel Forced On message class."""

from __future__ import annotations

from velbusaio.const import MessagePriority
from velbusaio.message_fields import ByteField, DeclarativeMessage

COMMAND_CODE = 0x15


class CancelForcedOn(DeclarativeMessage):
    """Cancel Forced On message."""

    _command_code = COMMAND_CODE
    _priority = MessagePriority.HIGH
    channel = ByteField(0)
