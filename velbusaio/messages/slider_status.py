"""Slider Status Message.

:author: Frank van Breugel
"""

from __future__ import annotations

from velbusaio.const import MessagePriority
from velbusaio.message_fields import ByteField, ChannelField, DeclarativeMessage

COMMAND_CODE = 0x0F


class SliderStatusMessage(DeclarativeMessage):
    """Slider Status Message."""

    _command_code = COMMAND_CODE
    _priority = MessagePriority.HIGH
    _data_length = 3

    channel = ChannelField(0)
    slider_state = ByteField(1)
    slider_long_pressed = ByteField(2)

    def cur_slider_state(self):
        """:return: int"""
        return self.slider_state
