"""Switch to day message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.command_registry import register
from velbusaio.message_fields import DeclarativeMessage, Int16Field

COMMAND_CODE = 0xDC


@register(COMMAND_CODE)
class SwitchToDayMessage(DeclarativeMessage):
    """Switch to day message class."""

    _command_code = COMMAND_CODE
    _priority = None

    sleep = Int16Field(0, default=0)
