"""Set Edge Color message class."""

from __future__ import annotations

from enum import IntEnum

from velbusaio.message_fields import BitField, ByteField, DeclarativeMessage

COMMAND_CODE = 0xD4


class CustomColorPriority(IntEnum):
    """Custom Color Priority enum."""

    LOW_PRIORITY = 1
    MID_PRIORITY = 2
    HIGH_PRIORITY = 3


class SetEdgeColorMessage(DeclarativeMessage):
    """Set Edge Color message (DLC=4 variant)."""

    _command_code = COMMAND_CODE
    _priority = None

    apply_background_color = BitField(0, bit=0)
    apply_continuous_feedback_color = BitField(0, bit=1)
    custom_color_palette = BitField(0, bit=7)

    apply_to_left_edge = BitField(1, bit=0)
    apply_to_top_edge = BitField(1, bit=1)
    apply_to_right_edge = BitField(1, bit=2)
    apply_to_bottom_edge = BitField(1, bit=3)
    apply_to_all_pages = BitField(1, bit=7)

    color_idx = BitField(2, bit_range=(0, 4))
    custom_color_priority = BitField(
        2, bit_range=(5, 6), default=CustomColorPriority.LOW_PRIORITY
    )
    background_blinking = BitField(2, bit=7)


class SetCustomColorMessage(DeclarativeMessage):
    """Set Custom Color (Palette) message (DLC=6 variant)."""

    _command_code = COMMAND_CODE
    _auto_register = False

    palette_idx = BitField(0, bit_range=(0, 4))
    white_mode = BitField(1, bit=7)
    saturation = BitField(1, bit_range=(0, 6), default=127)
    red = ByteField(2)
    green = ByteField(3)
    blue = ByteField(4)
