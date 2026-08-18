"""Module SubType Message class.

author: Thomas Delaet <thomas@delaet.org>
"""

from __future__ import annotations

from velbusaio.message_fields import ByteField, DeclarativeMessage, Field, Int16Field

COMMAND_CODE = 0xB0
COMMAND_CODE_2 = 0xA7
COMMAND_CODE_3 = 0xA6


class ModuleSubTypeMessage(DeclarativeMessage):
    """Module SubType Message."""

    _command_code = COMMAND_CODE
    _generates_data_to_binary = False

    module_type = ByteField(0)
    serial = Int16Field(1)

    sub_address_1 = ByteField(3, default=0xFF)
    sub_address_2 = ByteField(4, default=0xFF)
    sub_address_3 = ByteField(5, default=0xFF)
    sub_address_4 = ByteField(6, default=0xFF)
    sub_address_offset: int = 0


    def module_name(self) -> str:
        """:return: str"""
        return "Unknown"
