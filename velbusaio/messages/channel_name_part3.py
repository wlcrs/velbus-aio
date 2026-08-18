"""Channel Name Part 3 message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.message_fields import (
    BitField,
    ByteField,
    ChannelField,
    DeclarativeMessage,
    StringField,
)

COMMAND_CODE = 0xF2


class ChannelNamePart3Message(DeclarativeMessage):
    """Channel Name Part 3 message."""

    _command_code = COMMAND_CODE
    _data_length = 5

    channel = ChannelField(0)
    name = StringField(1)


class ChannelNamePart3Message2(ChannelNamePart3Message):
    """Channel Name Part 3 message (integer channel)."""

    _generates_data_to_binary = False

    channel = ByteField(0)


class ChannelNamePart3Message3(ChannelNamePart3Message):
    """Channel Name Part 3 message (VMB1BL/VMB2BL)."""

    _generates_data_to_binary = False

    channel = BitField(0, bit_range=(1, 2))
