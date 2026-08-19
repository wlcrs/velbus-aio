"""Input domain channels (Button, ButtonCounter, Sensor, SensorNumber)."""

from __future__ import annotations

import asyncio

from velbusaio.channels import Channel
from velbusaio.config import ConfigParameter
from velbusaio.const import (
    ENERGY_KILO_WATT_HOUR,
    VOLUME_CUBIC_METER_HOUR,
    VOLUME_LITERS_HOUR,
    ButtonLedState,
)
from velbusaio.exceptions import VelbusConfigError
from velbusaio.message import Message
from velbusaio.messages.clear_led import ClearLedMessage
from velbusaio.messages.fast_blinking_led import FastBlinkingLedMessage
from velbusaio.messages.push_button_status import PushButtonStatusMessage
from velbusaio.messages.set_led import SetLedMessage
from velbusaio.messages.slow_blinking_led import SlowBlinkingLedMessage

_LED_STATE_MESSAGES: dict[ButtonLedState, type[Message]] = {
    ButtonLedState.OFF: ClearLedMessage,
    ButtonLedState.ON: SetLedMessage,
    ButtonLedState.SLOW: SlowBlinkingLedMessage,
    ButtonLedState.FAST: FastBlinkingLedMessage,
}


class Button(Channel):
    """A Button channel."""

    enabled: bool = True
    closed: bool = False
    led_state: ButtonLedState | None = None
    long: bool = False
    _saved_reaction_time: int | None = None

    async def set_closed(self, closed: bool, long: bool = False) -> None:
        """Update button contact state."""
        self.closed = closed
        self.long = long
        await self.maybe_status_update()

    async def set_led(self, state: str | ButtonLedState) -> None:
        """Update button LED state."""
        self.led_state = ButtonLedState(state) if isinstance(state, str) else state
        await self.maybe_status_update()

    def get_categories(self) -> list[str]:
        """Return the categories for this channel."""
        if self.enabled:
            return ["binary_sensor", "led", "button"]
        return []

    def is_enabled(self) -> bool:
        """Return whether this channel is currently enabled."""
        return self.enabled

    def supports_channel_enable(self) -> bool:
        """Return True when EEPROM enable/disable is available."""
        return self.module.get_channel_enable_spec(self.channel_number) is not None

    async def get_channel_enabled(self, *, refresh: bool = False) -> bool | None:
        """Return EEPROM enable state (reaction time != disabled)."""
        spec = self.module.get_channel_enable_spec(self.channel_number)
        if spec is None:
            return None
        memory = self.module.memory
        if memory is None:
            return self.enabled
        value = await memory.read_byte(spec["address"], use_cache=not refresh)
        enabled = value != spec["disabled_value"]
        if enabled:
            self._saved_reaction_time = value
        self.enabled = enabled
        return enabled

    async def set_channel_enabled(self, enabled: bool) -> None:
        """Enable or disable this channel via the reaction-time EEPROM byte."""
        spec = self.module.get_channel_enable_spec(self.channel_number)
        if spec is None:
            raise VelbusConfigError(
                f"Channel {self.channel_number} does not support enable/disable"
            )
        memory = self.module.memory
        if memory is None:
            raise RuntimeError("Module memory backend is not initialized")
        current = await memory.read_byte(spec["address"])
        if current != spec["disabled_value"]:
            self._saved_reaction_time = current
        if enabled:
            value = (
                self._saved_reaction_time
                if self._saved_reaction_time not in (None, spec["disabled_value"])
                else spec["enabled_value"]
            )
        else:
            value = spec["disabled_value"]
        await memory.write_byte(spec["address"], value & 0xFF)
        self.enabled = enabled
        await self.maybe_status_update()

    def get_config_parameters(self) -> list[ConfigParameter]:
        """Return discoverable CONFIG parameters for this button channel."""
        params: list[ConfigParameter] = [
            ConfigParameter(
                key="name",
                label="Channel name",
                kind="text",
                getter=self._get_name_value,
                setter=self.set_name_persistent,
                max_length=16,
                channel=self.channel_number,
                entity=False,
            ),
        ]
        if self.supports_channel_enable():
            params.append(
                ConfigParameter(
                    key="enabled",
                    label="Enabled",
                    kind="bool",
                    getter=self._get_enabled_value,
                    setter=self.set_channel_enabled,
                    channel=self.channel_number,
                )
            )
        return params

    async def _get_name_value(self) -> str:
        return self.name

    async def _get_enabled_value(self) -> bool:
        enabled = await self.get_channel_enabled()
        return True if enabled is None else enabled

    def is_closed(self) -> bool:
        """Return if this button is on."""
        return self.closed

    def is_long_pressed(self) -> bool:
        """Return if this button is currently long pressed."""
        return self.long

    def is_on(self) -> bool:
        """Return if this button LED is on."""
        return self.led_state == ButtonLedState.ON

    async def set_led_state(self, state: str | ButtonLedState) -> None:
        """Set led."""
        if isinstance(state, str):
            state = ButtonLedState(state)

        _mod_add = self.address
        _chn_num = self.channel_number - self.module.calc_channel_offset(_mod_add)
        msg = self.create_message(_LED_STATE_MESSAGES[state], address=_mod_add)
        msg.leds = [_chn_num]
        await self.send_message(msg)
        self.led_state = state
        await self.maybe_status_update()

    async def press(self) -> None:
        """Press the button."""
        _mod_add = self.address
        _chn_num = self.channel_number - self.module.calc_channel_offset(_mod_add)
        # send the just pressed
        msg = self.create_message(PushButtonStatusMessage, address=_mod_add)
        msg.closed = [_chn_num]
        await self.send_message(msg)
        # wait
        await asyncio.sleep(0.3)
        # send the just released
        msg = self.create_message(PushButtonStatusMessage, address=_mod_add)
        msg.opened = [_chn_num]
        await self.send_message(msg)


class CounterChannel(Channel):
    """A Counter sensor channel."""

    Unit: str | None = None
    pulses: int | None = None
    counter: int | None = None
    delay: int | None = None
    power: int | float | None = None
    raw_energy: int | None = None

    async def update_counter(
        self, *, pulses: int, counter: int, delay: int | None = None
    ) -> None:
        """Update counter pulse parameters."""
        self.pulses = pulses
        self.counter = counter
        if delay is not None:
            self.delay = delay
        await self.maybe_status_update()

    async def update_values(
        self, *, power: int | float | None = None, energy: int | None = None
    ) -> None:
        """Update power and energy values."""
        if power is not None:
            self.power = power
        if energy is not None:
            self.raw_energy = energy
        await self.maybe_status_update()

    def get_categories(self) -> list[str]:
        """Return the categories for this channel."""
        return ["sensor"]

    def get_sensor_type(self) -> str:
        """Return the sensor type."""
        return "counter"

    @property
    def energy(self) -> float | None:
        """Return the accumulated energy in kWh, or None if not yet received."""
        if self.raw_energy is not None:
            return round(self.raw_energy / 1000, 3)
        if (
            self.counter is not None
            and self.pulses
            and self.Unit == ENERGY_KILO_WATT_HOUR
        ):
            return round(self.counter / self.pulses, 2)
        return None

    def _rate_from_pulse_interval(self) -> float:
        """Return the instantaneous rate derived from the interval between pulses."""
        if not self.delay or not self.pulses or not self.Unit or self.delay == 0xFFFF:
            return round(0, 2)
        if self.Unit in {VOLUME_LITERS_HOUR, VOLUME_CUBIC_METER_HOUR}:
            return round((1000 * 3600) / (self.delay * self.pulses), 2)
        if self.Unit == ENERGY_KILO_WATT_HOUR:
            return round((1000 * 1000 * 3600) / (self.delay * self.pulses), 2)
        return round(0, 2)

    def get_state(self) -> int | float:
        """Return the current state of the counter."""
        if self.raw_energy is not None:
            return self.raw_energy
        return self._rate_from_pulse_interval()

    def get_unit(self) -> str | None:
        """Return the unit of the counter."""
        if self.Unit == VOLUME_LITERS_HOUR:
            return "L"
        if self.Unit == VOLUME_CUBIC_METER_HOUR:
            return "m3"
        if self.Unit == ENERGY_KILO_WATT_HOUR:
            return "W"
        return None

    def set_unit(self, unit: str) -> None:
        """Set the unit of the counter."""
        self.Unit = unit

    def get_counter_state(self) -> int | float:
        """Return the instantaneous power (or flow) of the counter."""
        if self.power:
            return self.power
        return self._rate_from_pulse_interval()

    def get_counter_unit(self) -> str:
        """Return the unit of the counter."""
        return self.Unit or ""

    def is_water(self) -> bool:
        """Return if this channel is a water channel."""
        return bool(self.counter and self.Unit == VOLUME_LITERS_HOUR)


ButtonCounter = CounterChannel


class Sensor(Button):
    """A Sensor channel."""

    cur: float | None = None
    unit: str | None = None

    async def update_raw(self, cur: float, unit: str | None = None) -> None:
        """Update raw sensor value and optional unit."""
        self.cur = cur
        if unit is not None:
            self.unit = unit
        await self.maybe_status_update()

    def get_state(self) -> float | None:
        """Return current sensor state."""
        return self.cur

    def get_unit(self) -> str | None:
        """Return sensor unit."""
        return self.unit

    def get_categories(self) -> list[str]:
        """Return the categories for this channel."""
        if self.enabled:
            return ["binary_sensor", "led"]
        return []


class SensorNumber(Channel):
    """A Numeric Sensor channel."""

    cur: float = 0.0
    unit: str | None = None
    sensor_type: str | None = None
    min: float | None = None
    max: float | None = None

    async def update_number(self, cur: float) -> None:
        """Update sensor number value."""
        self.cur = cur
        await self.maybe_status_update()

    def get_categories(self) -> list[str]:
        """Return the categories for this channel."""
        return ["sensor"]

    def get_unit(self) -> str | None:
        """Return the unit of measurement for this channel."""
        return self.unit

    def get_state(self) -> float:
        """Return the current state of the sensor."""
        return round(self.cur, 2)

    def get_sensor_type(self) -> str | None:
        """Return the sensor type."""
        return self.sensor_type
