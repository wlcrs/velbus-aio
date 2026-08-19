"""Power domain message handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from velbusaio.message_router import register_handler
from velbusaio.messages.bus_error_counter_status import BusErrorCounterStatusMessage
from velbusaio.messages.psu_load import PsuLoadMessage
from velbusaio.messages.psu_values import PsuValuesMessage
from velbusaio.properties import (
    BusErrorOff,
    BusErrorRx,
    BusErrorTx,
    PSUCurrent,
    PSULoad,
    PSUPower,
    PSUVoltage,
)

if TYPE_CHECKING:
    from velbusaio.module import Module


@register_handler
async def handle_psu_values(module: Module, message: PsuValuesMessage) -> None:
    """Route PSU volt, amp, and watt readings."""
    suffix = "out" if message.channel == 3 else f"{message.channel}"
    props = module.get_properties().values()
    for prop in props:
        if suffix in prop.get_name():
            if isinstance(prop, PSUVoltage):
                await prop.update_value(message.volt)
            elif isinstance(prop, PSUCurrent):
                await prop.update_value(message.amp)
            elif isinstance(prop, PSUPower):
                await prop.update_value(message.watt)


@register_handler
async def handle_psu_load(module: Module, message: PsuLoadMessage) -> None:
    """Route PSU load readings."""
    for prop in module.get_properties().values():
        if isinstance(prop, PSULoad):
            name = prop.get_name()
            if name.endswith("out") or "out" in name:
                await prop.update_value(message.out)
            elif "1" in name:
                await prop.update_value(message.load_1)
            elif "2" in name:
                await prop.update_value(message.load_2)


@register_handler
async def handle_bus_error_counter(
    module: Module, message: BusErrorCounterStatusMessage
) -> None:
    """Route CAN bus error counters."""
    for prop in module.get_properties().values():
        if isinstance(prop, BusErrorOff):
            await prop.update_value(message.bus_off_counter)
        elif isinstance(prop, BusErrorRx):
            await prop.update_value(message.receive_error_counter)
        elif isinstance(prop, BusErrorTx):
            await prop.update_value(message.transmit_error_counter)
