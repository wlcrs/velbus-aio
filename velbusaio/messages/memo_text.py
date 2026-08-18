"""Memo Text Message.

:author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from velbusaio.message_fields import ByteField, DeclarativeMessage, StringField

COMMAND_CODE = 0xAC


class MemoTextMessage(DeclarativeMessage):
    """Memo Text Message."""

    _command_code = COMMAND_CODE
    _data_length = 7

    _dummy = ByteField(0)
    start = ByteField(1)
    name = StringField(2, length=5)
