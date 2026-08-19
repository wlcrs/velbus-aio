"""Input domain message handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from velbusaio.domains.input.channel import (
    Button,
    ButtonLedState,
    CounterChannel,
    Sensor,
)
from velbusaio.message_router import register_handler
from velbusaio.messages.clear_led import ClearLedMessage
from velbusaio.messages.counter_status import CounterStatusMessage
from velbusaio.messages.counter_value import CounterValueMessage
from velbusaio.messages.fast_blinking_led import FastBlinkingLedMessage
from velbusaio.messages.module_status import (
    ModuleStatusGP4PirMessage,
    ModuleStatusMessage,
    ModuleStatusMessage2,
    ModuleStatusPirMessage,
)
from velbusaio.messages.push_button_status import PushButtonStatusMessage
from velbusaio.messages.raw import SensorRawMessage
from velbusaio.messages.set_led import SetLedMessage
from velbusaio.messages.slow_blinking_led import SlowBlinkingLedMessage
from velbusaio.messages.update_led_status import UpdateLedStatusMessage
from velbusaio.properties import LightValue, SelectedProgram

if TYPE_CHECKING:
    from velbusaio.module import Module

_LOG = logging.getLogger("velbus-input")


def _get_button(module: Module, raw_channel: int | str) -> Button | None:
    channel_id = module.map_channel_number(raw_channel)
    chan = module.get_channels().get(channel_id)
    if isinstance(chan, Button) and not isinstance(chan, Sensor):
        return chan
    if chan is None or not isinstance(chan, CounterChannel):
        _LOG.warning(
            f"Received button message for non-existent button channel {raw_channel} (mapped: {channel_id}) on module {module.get_address()}"
        )
    return None


def _get_counter(module: Module, raw_channel: int | str) -> CounterChannel | None:
    channel_id = module.map_channel_number(raw_channel)
    chan = module.get_channels().get(channel_id)
    if isinstance(chan, CounterChannel):
        return chan
    if not module.is_loaded() and chan is not None:
        counter = CounterChannel(
            module=module,
            num=chan.get_channel_number(),
            name=chan.name,
            nameEditable=getattr(chan, "nameEditable", True),
            subDevice=chan.is_sub_device(),
            address=getattr(chan, "_address", module.get_address()),
        )
        module._channels[channel_id] = counter
        return counter
    _LOG.warning(
        f"Received counter message for non-existent counter channel {raw_channel} (mapped: {channel_id}) on module {module.get_address()}"
    )
    return None


def _get_sensor(module: Module, raw_channel: int | str) -> Sensor | None:
    channel_id = module.map_channel_number(raw_channel)
    sensors = {
        num: ch for num, ch in module.get_channels().items() if isinstance(ch, Sensor)
    }
    sensor = sensors.get(channel_id)
    if sensor is None:
        _LOG.warning(
            f"Received sensor message for non-existent sensor channel {raw_channel} (mapped: {channel_id}) on module {module.get_address()}"
        )
    return sensor


@register_handler
async def handle_push_button_status(
    module: Module, message: PushButtonStatusMessage
) -> None:
    """Route push button opened/closed status."""
    channel_offset = module.calc_channel_offset(message.address)
    for ch_id in message.closed:
        if btn := _get_button(module, ch_id + channel_offset):
            await btn.set_closed(True)
    for ch_id in message.opened:
        if btn := _get_button(module, ch_id + channel_offset):
            await btn.set_closed(False)


@register_handler
async def handle_counter_status(module: Module, message: CounterStatusMessage) -> None:
    """Route counter status."""
    if counter := _get_counter(module, message.channel):
        await counter.update_counter(
            pulses=message.pulses,
            counter=message.counter,
            delay=message.delay,
        )


@register_handler
async def handle_counter_value(module: Module, message: CounterValueMessage) -> None:
    """Route counter power/energy values."""
    if counter := _get_counter(module, message.channel):
        await counter.update_values(
            power=message.power,
            energy=message.energy,
        )


async def _update_buttons_from_list(
    module: Module,
    address: int,
    closed_channels: list[int],
    led_states: dict[int, str] | None = None,
) -> None:
    """Route button closed and LED state across 8 channels."""
    channel_offset = module.calc_channel_offset(address)
    for chan in range(1, 9):
        if btn := _get_button(module, chan + channel_offset):
            await btn.set_closed(chan in closed_channels)
            if led_states and chan in led_states:
                await btn.set_led(led_states[chan])


async def _update_selected_program(module: Module, selected_program: int) -> None:
    """Update SelectedProgram property from numeric code if present."""
    prog_prop = next(
        (p for p in module.get_properties().values() if isinstance(p, SelectedProgram)),
        None,
    )
    if prog_prop is not None:
        prog_map = {0: "none", 1: "summer", 2: "winter", 3: "holiday"}
        await prog_prop.update_value(prog_map.get(selected_program, "none"))


async def _update_light_value(module: Module, light_value: float) -> None:
    """Update LightValue property if present."""
    light_prop = next(
        (p for p in module.get_properties().values() if isinstance(p, LightValue)),
        None,
    )
    if light_prop is not None:
        await light_prop.update_value(light_value)


@register_handler
async def handle_module_status_gp4_pir(
    module: Module, message: ModuleStatusGP4PirMessage
) -> None:
    """Route GP4 PIR module status buttons, program, and light properties."""
    await _update_buttons_from_list(module, message.address, message.closed)
    await _update_selected_program(module, message.selected_program)
    await _update_light_value(module, message.light_value)


@register_handler
async def handle_module_status_pir(
    module: Module, message: ModuleStatusPirMessage
) -> None:
    """Route PIR module status sensor channels, program, and light properties."""
    channel_offset = module.calc_channel_offset(message.address)
    states = [
        message.dark,
        message.light,
        message.motion1,
        message.light_motion1,
        message.motion2,
        message.light_motion2,
        message.low_temp_alarm,
        message.high_temp_alarm,
    ]
    for chan, state in enumerate(states, start=1):
        if btn := _get_button(module, chan + channel_offset):
            await btn.set_closed(bool(state))
    await _update_selected_program(module, message.selected_program)
    await _update_light_value(module, message.light_value)


@register_handler
async def handle_module_status_2(module: Module, message: ModuleStatusMessage2) -> None:
    """Route ModuleStatusMessage2 buttons and program property."""
    await _update_buttons_from_list(module, message.address, message.closed)
    await _update_selected_program(module, message.selected_program)


@register_handler
async def handle_module_status(module: Module, message: ModuleStatusMessage) -> None:
    """Route standard ModuleStatusMessage buttons and LEDs."""
    led_states: dict[int, ButtonLedState] = {}
    for chan in range(1, 9):
        if chan in message.led_fast_blinking:
            led_states[chan] = ButtonLedState.FAST
        elif chan in message.led_slow_blinking:
            led_states[chan] = ButtonLedState.SLOW
        elif chan in message.led_on:
            led_states[chan] = ButtonLedState.ON
        else:
            led_states[chan] = ButtonLedState.OFF
    await _update_buttons_from_list(module, message.address, message.closed, led_states)


@register_handler
async def handle_update_led_status(
    module: Module, message: UpdateLedStatusMessage
) -> None:
    """Route LED updates across 8 channels."""
    channel_offset = module.calc_channel_offset(message.address)
    for chan in range(1, 9):
        if btn := _get_button(module, chan + channel_offset):
            await btn.set_led(message.get_led_state(chan))


@register_handler
async def handle_set_led(module: Module, message: SetLedMessage) -> None:
    channel_offset = module.calc_channel_offset(message.address)
    for chan in message.leds:
        if btn := _get_button(module, chan + channel_offset):
            await btn.set_led(ButtonLedState.ON)


@register_handler
async def handle_clear_led(module: Module, message: ClearLedMessage) -> None:
    channel_offset = module.calc_channel_offset(message.address)
    for chan in message.leds:
        if btn := _get_button(module, chan + channel_offset):
            await btn.set_led(ButtonLedState.OFF)


@register_handler
async def handle_slow_blinking_led(
    module: Module, message: SlowBlinkingLedMessage
) -> None:
    channel_offset = module.calc_channel_offset(message.address)
    for chan in message.leds:
        if btn := _get_button(module, chan + channel_offset):
            await btn.set_led(ButtonLedState.SLOW)


@register_handler
async def handle_fast_blinking_led(
    module: Module, message: FastBlinkingLedMessage
) -> None:
    channel_offset = module.calc_channel_offset(message.address)
    for chan in message.leds:
        if btn := _get_button(module, chan + channel_offset):
            await btn.set_led(ButtonLedState.FAST)


@register_handler
async def handle_sensor_raw(module: Module, message: SensorRawMessage) -> None:
    """Route raw analog sensor messages."""
    if sensor := _get_sensor(module, message.sensor):
        await sensor.update_raw(message.value, message.unit)
