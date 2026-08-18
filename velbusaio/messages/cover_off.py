"""Cover Off message.

:author: Tom Dupré <gitd8400@gmail.com>
"""

from __future__ import annotations

from velbusaio.const import MessagePriority
from velbusaio.message_fields import BlindChannelField, ChannelField, DeclarativeMessage

COMMAND_CODE = 0x04


class CoverOffMessage(DeclarativeMessage):
    """Cover Off message."""

    _command_code = COMMAND_CODE
    _priority = MessagePriority.HIGH
    _data_length = 1

    channel = ChannelField(0, default=0)


class CoverOffMessage2(CoverOffMessage):
    """Cover Off message."""

    channel = BlindChannelField(0, default=0)
