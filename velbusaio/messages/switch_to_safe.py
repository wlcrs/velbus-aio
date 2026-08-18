"""Switch to safe message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.message_fields import DeclarativeMessage, Int16Field

COMMAND_CODE = 0xDE


class SwitchToSafeMessage(DeclarativeMessage):
    """Switch to safe message class."""

    _command_code = COMMAND_CODE
    _priority = None

    sleep = Int16Field(0, default=0)
