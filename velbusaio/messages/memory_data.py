"""Memory Data Message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.message_fields import ByteField, DeclarativeMessage

COMMAND_CODE = 0xFE


class MemoryDataMessage(DeclarativeMessage):
    """Memory Data Message."""

    _command_code = COMMAND_CODE
    _data_length = 3

    high_address = ByteField(0)
    low_address = ByteField(1)
    data = ByteField(2)
