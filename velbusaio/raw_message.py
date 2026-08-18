"""Raw message representation and parsing for Velbus messages."""

from __future__ import annotations

from velbusaio.message import (
    Message,
    ParseError,
    RawMessage,
    _parse_raw_frame,
    _trim_buffer_garbage,
)

__all__ = ["Message", "ParseError", "RawMessage", "create"]


def create(rawmessage: bytearray) -> tuple[Message | None, bytearray]:
    """Create a RawMessage/Message from a bytearray buffer."""
    rawmessage = _trim_buffer_garbage(rawmessage)
    while True:
        if len(rawmessage) < 6:
            return None, rawmessage
        try:
            msg_info, remaining = _parse_raw_frame(rawmessage)
            if msg_info is None:
                return None, rawmessage
            priority, address, rtr, data = msg_info
            return Message(
                address=address, priority=priority, rtr=rtr, data=data
            ), remaining
        except ParseError:
            rawmessage = _trim_buffer_garbage(rawmessage[1:])
