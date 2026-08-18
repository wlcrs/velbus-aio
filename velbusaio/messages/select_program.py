"""Select Program Message.

:author: Danny De Gaspari
"""

from __future__ import annotations

from velbusaio.message_fields import BitField, DeclarativeMessage

COMMAND_CODE = 0xB3


class SelectProgramMessage(DeclarativeMessage):
    """Select Program Message."""

    _command_code = COMMAND_CODE
    _data_length = 1

    select_program = BitField(0, bit_range=(0, 1), default=0, serializable=True)


    def __init__(self, address: int = 0, program: int = 0):
        """Initialize Select Program Message Object."""
        super().__init__(address)
        self.select_program = program
