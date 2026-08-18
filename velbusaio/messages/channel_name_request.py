"""Channel Name Request message.

:author: Thomas Delaet <thomas@delaet.org> and Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from velbusaio.message_fields import (
    ByteField,
    ChannelsField,
    DeclarativeMessage,
    Field,
)

COMMAND_CODE = 0xEF


class Vmb2blChannelsField(Field[list[int]]):
    """Field for VMB2BL channel name request channels."""

    def parse(self, data: bytes) -> list[int]:
        """Parse requested VMB2BL channels."""
        channels = []
        tmp = (data[0] >> 1) & 0x03
        if tmp & 0x01:
            channels.append(1)
        if tmp & 0x02:
            channels.append(2)
        return channels

    def serialize(self, channels: list[int]) -> bytes:
        """Serialize requested VMB2BL channels."""
        tmp = 0x00
        if isinstance(channels, list):
            if 1 in channels:
                tmp |= 0x03
            if 2 in channels:
                tmp |= 0x0C
        return bytes([tmp])


class ChannelNameRequestMessage(DeclarativeMessage):
    """Channel Name Request message."""

    _command_code = COMMAND_CODE
    _data_length = 1

    channels = ChannelsField(0)


class ChannelNameRequestMessage2(ChannelNameRequestMessage):
    """Channel Name Request message (VMB2BL)."""

    channels = Vmb2blChannelsField(0)




class ChannelNameRequestMessage3(ChannelNameRequestMessage):
    """Channel Name Request message (VMBDALI)."""

    channels = ByteField(0)
