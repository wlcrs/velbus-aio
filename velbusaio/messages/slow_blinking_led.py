"""Set Slow Blinking LED Message.

:author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.message_fields import ChannelsField, DeclarativeMessage

COMMAND_CODE = 0xF7


class SlowBlinkingLedMessage(DeclarativeMessage):
    """Set Slow Blinking LED Message."""

    _command_code = COMMAND_CODE
    _data_length = 1

    leds = ChannelsField(0)
