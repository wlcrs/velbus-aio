"""Cover domain message handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from velbusaio.domains.cover.channel import Blind
from velbusaio.message_router import register_handler
from velbusaio.messages.blind_status import (
    BlindStatusMessage,
    BlindStatusNg20Message,
    BlindStatusNgMessage,
)

if TYPE_CHECKING:
    from velbusaio.module import Module

_LOG = logging.getLogger("velbus-cover")


def _get_blind(module: Module, raw_channel: int | str) -> Blind | None:
    channel_id = module.map_channel_number(raw_channel)
    blinds = {
        num: ch
        for num, ch in module.get_channels().items()
        if isinstance(ch, Blind)
    }
    blind = blinds.get(channel_id)
    if blind is None:
        _LOG.warning(
            f"Received blind status for non-existent blind channel {raw_channel} (mapped: {channel_id}) on module {module.get_address()}"
        )
    return blind


@register_handler
async def handle_blind_status_ng20(
    module: Module, message: BlindStatusNg20Message
) -> None:
    """Route dual-channel NG20 blind status messages."""
    for i in range(2):
        if blind := _get_blind(module, message.channel[i]):
            await blind.update_status(message.status[i], message.position[i])


@register_handler
async def handle_blind_status_ng(
    module: Module, message: BlindStatusNgMessage
) -> None:
    """Route NG blind status messages with position."""
    if blind := _get_blind(module, message.channel):
        await blind.update_status(message.status, message.position)


@register_handler
async def handle_blind_status(
    module: Module, message: BlindStatusMessage
) -> None:
    """Route standard single-channel blind status messages."""
    if blind := _get_blind(module, message.channel):
        await blind.update_status(message.status)
