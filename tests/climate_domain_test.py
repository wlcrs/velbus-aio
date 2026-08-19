"""Tests for the Climate domain package (channels and message handlers)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from velbusaio.domains.climate import (
    Temperature,
    ThermostatChannel,
)
from velbusaio.message import Message
from velbusaio.messages.sensor_temperature import SensorTemperatureMessage
from velbusaio.messages.temp_sensor_settings_part1 import TempSensorSettingsPart1
from velbusaio.messages.temp_sensor_settings_part2 import TempSensorSettingsPart2
from velbusaio.messages.temp_sensor_settings_part3 import TempSensorSettingsPart3
from velbusaio.messages.temp_sensor_settings_part4 import TempSensorSettingsPart4
from velbusaio.messages.temp_sensor_status import TempSensorStatusMessage
from velbusaio.module import Module


@pytest.mark.asyncio
async def test_climate_domain_status_routing(mock_controller):
    """Test dispatching TempSensorStatus to Temperature and ThermostatChannel."""
    module = Module(1, 0x34, controller=mock_controller)

    temp_channel = Temperature(module, 34, "Temperature", False, True, 1)
    heater_channel = ThermostatChannel(module, 35, "Heater", False, True, 1)
    boost_channel = ThermostatChannel(module, 36, "Boost", False, True, 1)

    module.channels[34] = temp_channel
    module.channels[35] = heater_channel
    module.channels[36] = boost_channel

    # Simulate TempSensorStatus message
    status_msg = TempSensorStatusMessage(1)
    status_msg.target_temp = 21.5
    status_msg.current_temp = 20.0
    status_msg.mode = 4  # comfort
    status_msg.status_mode = 0  # run
    status_msg.heater = True
    status_msg.boost = False

    await module.on_message(status_msg)

    assert temp_channel.get_climate_target() == 21.5
    assert temp_channel.get_climate_preset() == "comfort"
    assert temp_channel.get_climate_mode() == "run"
    assert heater_channel.is_closed() is True
    assert boost_channel.is_closed() is False


@pytest.mark.asyncio
async def test_climate_domain_sensor_temperature(mock_controller):
    """Test routing SensorTemperatureMessage to Temperature channel."""
    module = Module(1, 0x34, controller=mock_controller)

    temp_channel = Temperature(module, 34, "Temperature", False, True, 1)
    module.channels[34] = temp_channel

    msg = SensorTemperatureMessage(1)
    msg.cur = 22.25
    msg.min = 18.0
    msg.max = 25.0

    await module.on_message(msg)

    assert temp_channel.get_state() == 22.25
    assert temp_channel.get_min() == 18.0
    assert temp_channel.get_max() == 25.0


@pytest.mark.asyncio
async def test_climate_domain_settings_parts(mock_controller):
    """Test routing TempSensorSettingsPart1-4 directly to Temperature."""
    module = Module(1, 0x34, controller=mock_controller)
    temp_channel = Temperature(module, 34, "Temperature", False, True, 1)
    module.channels[34] = temp_channel

    part1 = TempSensorSettingsPart1(1)
    part1.comfort_heating = 21.5
    part1.day_heating = 20.0
    part1.night_heating = 18.0
    part1.antifreeze_heating = 7.0
    part1.temp_difference = 2.0
    part1.hysteresis = 0.5
    await module.on_message(part1)

    assert temp_channel.get_setting("comfort_heating") == 21.5
    assert temp_channel.get_setting("day_heating") == 20.0
    assert temp_channel.get_setting("night_heating") == 18.0
    assert temp_channel.get_setting("hysteresis") == 0.5

    part2 = TempSensorSettingsPart2(1)
    part2.comfort_cooling = 24.0
    part2.default_sleep_timer = 45
    part2.autosend_interval = 60
    await module.on_message(part2)

    assert temp_channel.get_setting("comfort_cooling") == 24.0
    assert temp_channel.get_setting("default_sleep_timer") == 45
    assert temp_channel.get_setting("autosend_interval") == 60

    part3 = TempSensorSettingsPart3(1)
    part3.alarm_low = 5.0
    part3.alarm_high = 35.0
    await module.on_message(part3)

    assert temp_channel.get_setting("alarm_low") == 5.0
    assert temp_channel.get_setting("alarm_high") == 35.0

    part4 = TempSensorSettingsPart4(1)
    part4.min_switching_time = 3
    await module.on_message(part4)

    assert temp_channel.get_setting("min_switching_time") == 3


def test_extract_message_types_deduction():
    """Test that extract_message_types deduces message types from single and union annotations."""
    from velbusaio.message_router import extract_message_types

    def single_type_handler(module: Any, message: SensorTemperatureMessage) -> None:
        pass

    def union_type_handler(
        module: Any, message: TempSensorSettingsPart1 | TempSensorStatusMessage
    ) -> None:
        pass

    assert extract_message_types(single_type_handler) == (SensorTemperatureMessage,)
    assert extract_message_types(union_type_handler) == (
        TempSensorSettingsPart1,
        TempSensorStatusMessage,
    )
