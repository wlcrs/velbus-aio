"""Switch Relay On Message."""

from __future__ import annotations

from velbusaio.command_registry import register
from velbusaio.message_fields import (
    ChannelIndexField,
    ChannelsField,
    DeclarativeMessage,
)

COMMAND_CODE = 0x02


@register(COMMAND_CODE)
class SwitchRelayOnMessage(DeclarativeMessage):
    """Switch Relay On Message."""

    _command_code = COMMAND_CODE
    _priority = "high"
    _data_length = 1

    relay_channels = ChannelsField(0)


@register(COMMAND_CODE)
class SwitchRelayOnMessage20(SwitchRelayOnMessage):
    """Switch Relay On Message for -20 series."""

    relay_channels = ChannelIndexField(0)
