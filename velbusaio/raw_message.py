"""RawMessage compatibility alias for Message."""

from __future__ import annotations

from velbusaio.message import Message, ParseError, _parse_raw_frame

RawMessage = Message
create_message_info = _parse_raw_frame

__all__ = ["Message", "ParseError", "RawMessage", "create_message_info"]
