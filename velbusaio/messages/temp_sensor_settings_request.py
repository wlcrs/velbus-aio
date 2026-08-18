"""TempSensorSettingsRequest message implementation.

:author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from velbusaio.message_fields import DeclarativeMessage

COMMAND_CODE = 0xE7


class TempSensorSettingsRequest(DeclarativeMessage):
    """TempSensorSettingsRequest message class."""

    _command_code = COMMAND_CODE
