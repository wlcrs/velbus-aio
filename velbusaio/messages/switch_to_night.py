"""Switch to night message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.message_fields import DeclarativeMessage, Int16Field

COMMAND_CODE = 0xDD


class SwitchToNightMessage(DeclarativeMessage):
    """Switch to night message class."""

    _command_code = COMMAND_CODE
    _priority = None

    sleep = Int16Field(0)
