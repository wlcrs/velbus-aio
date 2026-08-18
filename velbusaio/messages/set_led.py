"""Set led Message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.message_fields import ChannelsField, DeclarativeMessage

COMMAND_CODE = 0xF6


class SetLedMessage(DeclarativeMessage):
    """Set led Message."""

    _command_code = COMMAND_CODE
    _data_length = 1

    leds = ChannelsField(0)
