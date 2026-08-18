"""Module Type Request Message class.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.const import MessagePriority
from velbusaio.message_fields import DeclarativeMessage


class ModuleTypeRequestMessage(DeclarativeMessage):
    """Module Type Request Message."""

    _priority = MessagePriority.LOW
    _rtr = True
    _data_length = 0
