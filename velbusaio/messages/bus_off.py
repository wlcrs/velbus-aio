"""Bus Off message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.message_fields import DeclarativeMessage

COMMAND_CODE = 0x09


class BusOffMessage(DeclarativeMessage):
    """Bus Off message."""

    _command_code = COMMAND_CODE
    _data_length = 0
