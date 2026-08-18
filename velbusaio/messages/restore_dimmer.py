"""Restore Dimmer Message.

:author: Frank van Breugel
"""

from __future__ import annotations

from velbusaio.const import MessagePriority
from velbusaio.message_fields import (
    ByteField,
    ChannelIndexField,
    ChannelsField,
    DeclarativeMessage,
    Field,
)

COMMAND_CODE = 0x11


def _parse_transition(data: bytes) -> int:
    return int.from_bytes(data[2:4], byteorder="big", signed=False)


def _serialize_transition(value: int) -> bytes:
    return value.to_bytes(2, byteorder="big", signed=False)


class RestoreDimmerMessage(DeclarativeMessage):
    """Restore Dimmer Message.

    With this message the channel numbering is a bitnumber.
    """

    _command_code = COMMAND_CODE
    _priority = MessagePriority.HIGH
    _data_length = 4

    dimmer_channels = ChannelsField(0)
    _padding = ByteField(1, default=0)
    dimmer_transitiontime = Field(
        default=0,
        parser=_parse_transition,
        serializer=_serialize_transition,
    )


class RestoreDimmerMessage2(RestoreDimmerMessage):
    """Restore Dimmer Message.

    With this message the channel numbering is an integer.
    """

    dimmer_channels = ChannelIndexField(0)
