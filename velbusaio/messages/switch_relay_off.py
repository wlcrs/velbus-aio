"""Switch Relay Off Message."""

from __future__ import annotations

from velbusaio.const import MessagePriority
from velbusaio.message_fields import (
    ChannelIndexField,
    ChannelsField,
    DeclarativeMessage,
)

COMMAND_CODE = 0x01


class SwitchRelayOffMessage(DeclarativeMessage):
    """Switch Relay Off Message."""

    _command_code = COMMAND_CODE
    _priority = MessagePriority.HIGH
    _data_length = 1

    relay_channels = ChannelsField(0)


class SwitchRelayOffMessage20(SwitchRelayOffMessage):
    """Switch Relay Off Message for -20 series."""

    relay_channels = ChannelIndexField(0)
