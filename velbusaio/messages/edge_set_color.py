"""Set Edge Color message class."""

from __future__ import annotations

from enum import IntEnum

from velbusaio.message_fields import BitField, ByteField, DeclarativeMessage, Field


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

    apply_background_color = BitField(0, bit=0, default=False)
    apply_continuous_feedback_color = BitField(0, bit=1, default=False)
    custom_color_palette = BitField(0, bit=7, default=False)

    apply_to_left_edge = BitField(1, bit=0, default=False)
    apply_to_top_edge = BitField(1, bit=1, default=False)
    apply_to_right_edge = BitField(1, bit=2, default=False)
    apply_to_bottom_edge = BitField(1, bit=3, default=False)
    apply_to_all_pages = BitField(1, bit=7, default=False)

    color_idx = BitField(2, bit_range=(0, 4), default=0)
    custom_color_priority = BitField(
        2, bit_range=(5, 6), default=CustomColorPriority.LOW_PRIORITY
    )
    background_blinking = BitField(2, bit=7, default=False)

    apply_slow_blinking_feedback_color = Field(default=False, serializable=False)
    apply_fast_blinking_feedback_color = Field(default=False, serializable=False)
    apply_to_page = Field(default=None, serializable=False)


class SetCustomColorMessage(DeclarativeMessage):
    """Set Custom Color (Palette) message (DLC=6 variant)."""

    _command_code = COMMAND_CODE
    _auto_register = False

    palette_idx = BitField(0, bit_range=(0, 4), default=0)
    white_mode = BitField(1, bit=7, default=False)
    saturation = BitField(1, bit_range=(0, 6), default=127)
    red = ByteField(2, default=0)
    green = ByteField(3, default=0)
    blue = ByteField(4, default=0)


