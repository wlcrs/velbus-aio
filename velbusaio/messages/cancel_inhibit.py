"""Cancel Inhibit message class."""

from __future__ import annotations

from velbusaio.const import MessagePriority
from velbusaio.message_fields import ByteField, DeclarativeMessage

COMMAND_CODE = 0x17


class CancelInhibit(DeclarativeMessage):
    """Cancel Inhibit message."""

    _command_code = COMMAND_CODE
    _priority = MessagePriority.HIGH
    channel = ByteField(0)
