"""Switch to night message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.command_registry import register
from velbusaio.message_fields import DeclarativeMessage, Int16Field

COMMAND_CODE = 0xDD


@register(COMMAND_CODE)
class SwitchToNightMessage(DeclarativeMessage):
    """Switch to night message class."""

    _command_code = COMMAND_CODE
    _priority = None

    sleep = Int16Field(0, default=0)
