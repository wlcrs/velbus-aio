"""Light Value Request message class.

:author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from velbusaio.message_fields import DeclarativeMessage

COMMAND_CODE = 0xAA


class LightValueRequest(DeclarativeMessage):
    """Light Value Request message."""

    _command_code = COMMAND_CODE
