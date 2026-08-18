"""Cover Down message.

:author: Tom Dupré <gitd8400@gmail.com>
"""

from __future__ import annotations

from velbusaio.const import MessagePriority
from velbusaio.message_fields import (
    BlindChannelField,
    ChannelField,
    DeclarativeMessage,
    Int24Field,
)

COMMAND_CODE = 0x06


class CoverDownMessage(DeclarativeMessage):
    """Cover Down message."""

    _command_code = COMMAND_CODE
    _priority = MessagePriority.HIGH
    _data_length = 4

    channel = ChannelField(0, default=0)
    delay_time = Int24Field(1)


class CoverDownMessage2(CoverDownMessage):
    """Cover Down message."""

    channel = BlindChannelField(0, default=0)
