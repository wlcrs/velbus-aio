"""Counter Status Request message.

:author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from velbusaio.command_registry import register
from velbusaio.message_fields import ByteField, ChannelsField, DeclarativeMessage

COMMAND_CODE = 0xBD


@register(COMMAND_CODE)
class CounterStatusRequestMessage(DeclarativeMessage):
    """Counter Status Request message."""

    _command_code = COMMAND_CODE
    _data_length = 2

    wait_after_send = 500

    channels = ChannelsField(0)
    dummy = ByteField(1, default=0x00)
