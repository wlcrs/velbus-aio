"""Channel Clear LED message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.message_fields import ChannelsField, DeclarativeMessage

COMMAND_CODE = 0xF5


class ClearLedMessage(DeclarativeMessage):
    """Channel Clear LED message."""

    _command_code = COMMAND_CODE
    _data_length = 1

    leds = ChannelsField(0)
