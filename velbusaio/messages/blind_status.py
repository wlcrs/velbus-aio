"""Blind Status message.

:author: Tom Dupré <gitd8400@gmail.com>
"""

from __future__ import annotations

import json

from velbusaio.const import PRIORITY_LOW, MessagePriority
from velbusaio.message import Message
from velbusaio.message_fields import (
    BlindChannelField,
    BlindStatusField,
    ByteField,
    ChannelField,
    DeclarativeMessage,
)

COMMAND_CODE = 0xEC
DSTATUS = {0: "off", 1: "up", 2: "down"}


class BlindStatusNgMessage(DeclarativeMessage):
    """Blind Status NG message."""

    _command_code = COMMAND_CODE
    _data_length = 7
    _generates_data_to_binary = False

    channel = ChannelField(0)
    timeout = ByteField(1)
    status = ByteField(2, json_map=DSTATUS)
    position = ByteField(4, default=None)

    def is_moving_up(self) -> bool:
        """Is moving up."""
        return self.status == 0x01

    def is_moving_down(self) -> bool:
        """Is moving down."""
        return self.status == 0x02

    def is_stopped(self) -> bool:
        """Is stopped."""
        return self.status == 0x00


class BlindStatusNg20Message(BlindStatusNgMessage):
    """Blind Status NG20 message."""

    def __init__(self, address: int = 0) -> None:
        """Initialize BlindStatusNg20Message class."""
        Message.__init__(self, address=address)
        self.channel = (1, 2)
        self.timeout = 0
        self.status = (0, 0)
        self.position = (0, 0)

    @classmethod
    def from_bytes(
        cls,
        data: bytes | bytearray,
        address: int = 0,
        priority: int = PRIORITY_LOW,
        rtr: bool = False,
    ) -> BlindStatusNg20Message:
        """Parse BlindStatusNg20Message from raw payload bytes."""
        data_bytes = bytes(data)
        msg = cls(address=address)
        msg.needs_low_priority(priority)
        msg.needs_no_rtr(rtr)
        msg.needs_data(data_bytes, 7)
        msg.priority = (
            MessagePriority(priority)
            if isinstance(priority, int)
            and priority in MessagePriority._value2member_map_
            else priority
        )  # type: ignore[assignment]
        msg.rtr = rtr
        channel1_status = data_bytes[0] & 0x03
        channel2_status = (data_bytes[0] >> 4) & 0x03
        msg.status = (channel1_status, channel2_status)
        msg.position = (data_bytes[1], data_bytes[2])
        return msg

    def to_json(self):
        """To json."""
        json_dict = self.to_json_basic()
        json_dict["channel"] = self.channel
        json_dict["timeout"] = self.timeout
        json_dict["position"] = self.position
        json_dict["status"] = (DSTATUS[self.status[0]], DSTATUS[self.status[1]])
        return json.dumps(json_dict)


class BlindStatusMessage(DeclarativeMessage):
    """Blind Status message."""

    _command_code = COMMAND_CODE
    _data_length = 7
    _generates_data_to_binary = False

    channel = BlindChannelField(0)
    timeout = ByteField(1)
    status = BlindStatusField(2, json_map=DSTATUS)

    def is_moving_up(self) -> bool:
        """Is moving up."""
        return self.status == 0x01

    def is_moving_down(self) -> bool:
        """Is moving down."""
        return self.status == 0x02

    def is_stopped(self) -> bool:
        """Is stopped."""
        return self.status == 0x00
