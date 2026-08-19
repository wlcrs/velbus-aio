"""Climate domain message handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from velbusaio.domains.climate.channel import Temperature, ThermostatChannel
from velbusaio.message_router import register_handler
from velbusaio.messages.sensor_temperature import SensorTemperatureMessage
from velbusaio.messages.temp_sensor_settings_part1 import TempSensorSettingsPart1
from velbusaio.messages.temp_sensor_settings_part2 import TempSensorSettingsPart2
from velbusaio.messages.temp_sensor_settings_part3 import TempSensorSettingsPart3
from velbusaio.messages.temp_sensor_settings_part4 import TempSensorSettingsPart4
from velbusaio.messages.temp_sensor_status import TempSensorStatusMessage

if TYPE_CHECKING:
    from velbusaio.module import Module


def _get_temp_channels(module: Module) -> list[Temperature]:
    return [ch for ch in module.channels.values() if isinstance(ch, Temperature)]


def _get_thermostat_channels(module: Module) -> list[ThermostatChannel]:
    return [
        ch for ch in module.channels.values() if isinstance(ch, ThermostatChannel)
    ]


@register_handler
async def handle_sensor_temperature(
    module: Module, message: SensorTemperatureMessage
) -> None:
    """Route incoming temperature sensor readings."""
    for temp_ch in _get_temp_channels(module):
        await temp_ch.update_sensor_temperature(
            cur=message.cur, min_temp=message.min, max_temp=message.max
        )


@register_handler
async def handle_temp_sensor_status(
    module: Module, message: TempSensorStatusMessage
) -> None:
    """Route incoming thermostat status."""
    for temp_ch in _get_temp_channels(module):
        await temp_ch.update_thermostat_status(
            target_temp=message.target_temp,
            mode=message.mode,
            status_mode=message.status_mode,
            sleep_timer=message.sleep_timer,
            cool_mode=message.cool_mode,
            current_temp=message.current_temp,
        )
    for therm_ch in _get_thermostat_channels(module):
        await therm_ch.update_status_from_message(message)


@register_handler
async def handle_temp_settings_part1(
    module: Module, message: TempSensorSettingsPart1
) -> None:
    """Route Part1 settings to temperature channels."""
    for temp_ch in _get_temp_channels(module):
        await temp_ch.update_settings_part1(
            current_set=message.current_set,
            comfort_heating=message.comfort_heating,
            day_heating=message.day_heating,
            night_heating=message.night_heating,
            antifreeze_heating=message.antifreeze_heating,
            temp_difference=message.temp_difference,
            hysteresis=message.hysteresis,
        )


@register_handler
async def handle_temp_settings_part2(
    module: Module, message: TempSensorSettingsPart2
) -> None:
    """Route Part2 settings to temperature channels."""
    for temp_ch in _get_temp_channels(module):
        await temp_ch.update_settings_part2(
            comfort_cooling=message.comfort_cooling,
            day_cooling=message.day_cooling,
            night_cooling=message.night_cooling,
            safe_cooling=message.safe_cooling,
            default_sleep_timer=message.default_sleep_timer,
            autosend_interval=message.autosend_interval,
        )


@register_handler
async def handle_temp_settings_part3(
    module: Module, message: TempSensorSettingsPart3
) -> None:
    """Route Part3 settings to temperature channels."""
    for temp_ch in _get_temp_channels(module):
        await temp_ch.update_settings_part3(
            alarm_low=message.alarm_low,
            alarm_high=message.alarm_high,
            cool_lower=message.cool_lower,
            heat_upper=message.heat_upper,
            calibration=message.calibration,
            slave_or_zone=message.slave_or_zone,
            calibration_gain=message.calibration_gain,
        )


@register_handler
async def handle_temp_settings_part4(
    module: Module, message: TempSensorSettingsPart4
) -> None:
    """Route Part4 settings to temperature channels."""
    for temp_ch in _get_temp_channels(module):
        await temp_ch.update_settings_part4(
            min_switching_time=message.min_switching_time,
            pump_delayed_on=message.pump_delayed_on,
            pump_delayed_off=message.pump_delayed_off,
            alarm_2=message.alarm_2,
            alarm_3=message.alarm_3,
            heat_lower=message.heat_lower,
            cool_upper=message.cool_upper,
        )
