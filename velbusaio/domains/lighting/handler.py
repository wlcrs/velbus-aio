"""Lighting domain message handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from velbusaio.domains.lighting.channel import Dimmer, Relay
from velbusaio.message_router import register_handler
from velbusaio.messages.cancel_forced_off import CancelForcedOff
from velbusaio.messages.cancel_forced_on import CancelForcedOn
from velbusaio.messages.cancel_inhibit import CancelInhibit
from velbusaio.messages.dali_dim_value_status import DimValueStatus
from velbusaio.messages.dimmer_channel_status import DimmerChannelStatusMessage
from velbusaio.messages.dimmer_status import DimmerStatusMessage
from velbusaio.messages.forced_off import ForcedOff
from velbusaio.messages.forced_on import ForcedOn
from velbusaio.messages.inhibit import Inhibit
from velbusaio.messages.relay_status import (
    RelayStatusMessage,
    RelayStatusMessage2,
    RelayStatusMessage3,
)
from velbusaio.messages.slider_status import SliderStatusMessage

if TYPE_CHECKING:
    from velbusaio.module import Module

_LOG = logging.getLogger("velbus-lighting")


def _get_relay(module: Module, raw_channel: int | str) -> Relay | None:
    channel_id = module.map_channel_number(raw_channel)
    relays = {
        num: ch for num, ch in module.channels.items() if isinstance(ch, Relay)
    }
    relay = relays.get(channel_id)
    if relay is None:
        _LOG.warning(
            f"Received relay message for non-existent relay channel {raw_channel} (mapped: {channel_id}) on module {module.address}"
        )
    return relay


def _get_dimmer(module: Module, raw_channel: int | str) -> Dimmer | None:
    channel_id = module.map_channel_number(raw_channel)
    dimmers = {
        num: ch for num, ch in module.channels.items() if isinstance(ch, Dimmer)
    }
    dimmer = dimmers.get(channel_id)
    if dimmer is None:
        _LOG.warning(
            f"Received dimmer message for non-existent dimmer channel {raw_channel} (mapped: {channel_id}) on module {module.address}"
        )
    return dimmer


@register_handler
async def handle_relay_status(
    module: Module, message: RelayStatusMessage | RelayStatusMessage2
) -> None:
    """Route single-channel relay status."""
    if relay := _get_relay(module, message.channel):
        await relay.update_status(
            on=message.is_on(),
            inhibit=message.is_inhibited(),
            forced_on=message.is_forced_on(),
            disabled=message.is_disabled(),
        )


@register_handler
async def handle_relay_status_3(module: Module, message: RelayStatusMessage3) -> None:
    """Route multi-channel RelayStatusMessage3."""
    channel_offset = module.calc_channel_offset(message.address)
    for chan in range(1, 5):
        if relay := _get_relay(module, chan + channel_offset):
            await relay.update_status(
                on=message.is_on(chan),
                inhibit=message.is_inhibited(chan),
                forced_on=message.is_forced_on(chan),
                forced_off=message.is_forced_off(chan),
                disabled=message.is_program_disabled(chan),
            )


@register_handler
async def handle_forced_on(module: Module, message: ForcedOn) -> None:
    if relay := _get_relay(module, message.channel):
        await relay.set_forced_on_state(True)


@register_handler
async def handle_forced_off(module: Module, message: ForcedOff) -> None:
    if relay := _get_relay(module, message.channel):
        await relay.set_forced_off_state(True)


@register_handler
async def handle_inhibit(module: Module, message: Inhibit) -> None:
    if relay := _get_relay(module, message.channel):
        await relay.set_inhibit_state(True)


@register_handler
async def handle_cancel_forced_on(module: Module, message: CancelForcedOn) -> None:
    if relay := _get_relay(module, message.channel):
        await relay.set_forced_on_state(False)


@register_handler
async def handle_cancel_forced_off(module: Module, message: CancelForcedOff) -> None:
    if relay := _get_relay(module, message.channel):
        await relay.set_forced_off_state(False)


@register_handler
async def handle_cancel_inhibit(module: Module, message: CancelInhibit) -> None:
    if relay := _get_relay(module, message.channel):
        await relay.set_inhibit_state(False)


@register_handler
async def handle_dimmer_status(
    module: Module, message: DimmerStatusMessage | DimmerChannelStatusMessage
) -> None:
    """Route dimmer status."""
    if dimmer := _get_dimmer(module, message.channel):
        await dimmer.update_dimmer_state(message.cur_dimmer_state())


@register_handler
async def handle_slider_status(module: Module, message: SliderStatusMessage) -> None:
    """Route slider status."""
    if dimmer := _get_dimmer(module, message.channel):
        await dimmer.update_dimmer_state(message.cur_slider_state())


@register_handler
async def handle_dim_value_status(module: Module, message: DimValueStatus) -> None:
    """Route DALI DimValueStatus across offset channels."""
    for offset, dim_value in enumerate(message.dim_values):
        if dimmer := _get_dimmer(module, message.channel + offset):
            await dimmer.update_dimmer_state(dim_value)
