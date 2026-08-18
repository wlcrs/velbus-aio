"""Module Status Request Message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.command_registry import register
from velbusaio.message_fields import ChannelsField, DeclarativeMessage

COMMAND_CODE = 0xFA


@register(COMMAND_CODE)
class ModuleStatusRequestMessage(DeclarativeMessage):
    """Module Status Request Message."""

    _command_code = COMMAND_CODE
    _data_length = 1

    wait_after_send = 500
    channels = ChannelsField(0)
