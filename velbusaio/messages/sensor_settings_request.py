"""Sensor Settings Request Message.

:author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from velbusaio.const import MessagePriority
from velbusaio.message_fields import DeclarativeMessage

COMMAND_CODE = 0xE7


class SensorSettingsRequestMessage(DeclarativeMessage):
    """Sensor Settings Request Message."""

    _command_code = COMMAND_CODE
    _priority = MessagePriority.LOW
    _rtr = True
    _data_length = 0
