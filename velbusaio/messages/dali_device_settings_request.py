"""Dali Device Settings Request message.

:author: Niels Laukens
"""

from __future__ import annotations

import enum

from velbusaio.message_fields import ByteField, DeclarativeMessage, Field
from velbusaio.messages.dali_device_settings import DaliDeviceSetting

COMMAND_CODE = 0xE7


class DataSource(enum.Enum):
    """Data source enum."""

    FromMemory = 0
    FromDaliDevice = 1


class DaliDeviceSettingsRequest(DeclarativeMessage):
    """Dali Device Settings Request message."""

    _command_code = COMMAND_CODE
    _data_length = 2

    channel = ByteField(0, default=None)
    data_source = Field(
        1,
        parser=lambda data: DataSource(data[1]) if len(data) > 1 else None,
        default=DataSource.FromMemory,
        serializable=False,
    )
    settings = ByteField(2, default=None, serializable=False)




    def data_to_binary(self) -> bytes:
        """Generate binary data for the message."""
        assert self.channel is not None
        data = bytearray([COMMAND_CODE, self.channel, DataSource.FromMemory.value])
        if isinstance(self.settings, DaliDeviceSetting):
            data.append(self.settings.value)
        elif self.settings is not None:
            data.append(self.settings)
        return bytes(data)
