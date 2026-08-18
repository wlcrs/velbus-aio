"""Switch Relay On Message."""

from __future__ import annotations

from velbusaio.const import MessagePriority
from velbusaio.message_fields import (
    ChannelIndexField,
    ChannelsField,
    DeclarativeMessage,
)

COMMAND_CODE = 0x02


class SwitchRelayOnMessage(DeclarativeMessage):
    """Switch Relay On Message."""

    _command_code = COMMAND_CODE
    _priority = MessagePriority.HIGH
    _data_length = 1

    relay_channels = ChannelsField(0)


class SwitchRelayOnMessage20(SwitchRelayOnMessage):
    """Switch Relay On Message for -20 series."""

    relay_channels = ChannelIndexField(0)
