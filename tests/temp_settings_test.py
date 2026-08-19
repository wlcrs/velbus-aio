"""Tests for temperature sensor settings on Temperature channel."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from velbusaio.domains.climate.channel import (
    Temperature,
    infer_temp_settings_layout,
    module_supports_temp_settings,
)
from velbusaio.exceptions import VelbusConfigError
from velbusaio.messages.temp_sensor_settings_part1 import TempSensorSettingsPart1
from velbusaio.messages.temp_sensor_settings_part2 import TempSensorSettingsPart2
from velbusaio.messages.temp_sensor_settings_part3 import TempSensorSettingsPart3
from velbusaio.messages.temp_sensor_settings_part4 import TempSensorSettingsPart4
from velbusaio.messages.temp_sensor_settings_request import TempSensorSettingsRequest
from velbusaio.module import Module


class TestModuleSupport:
    """Module capability helpers."""

    def test_supports_vmb1ts(self):
        """VMB1TS advertises full settings."""
        data = {
            "Type": "VMB1TS",
            "TemperatureChannel": "01",
            "CommandToClass": {
                "E7": "TempSensorSettingsRequest",
                "E8": "TempSensorSettingsPart1",
                "E9": "TempSensorSettingsPart2",
                "C6": "TempSensorSettingsPart3",
                "B9": "TempSensorSettingsPart4",
            },
        }
        assert module_supports_temp_settings(data)
        assert infer_temp_settings_layout(data) == "classic"

    def test_rejects_dali_command_overlap(self):
        """DALI also uses 0xE7/0xE8 but is not a temp sensor."""
        data = {
            "Type": "VMBDALI",
            "CommandToClass": {
                "E7": "TempSensorSettingsRequest",
                "E8": "TempSensorSettingsPart1",
            },
        }
        assert not module_supports_temp_settings(data)

    def test_gp_layout(self):
        """Glass panels use the GP Part3/4 layout."""
        assert (
            infer_temp_settings_layout({"Type": "VMBGP4", "TempSettingsLayout": "gp"})
            == "gp"
        )


class TestTemperatureSettings:
    """Temperature channel settings update and write behaviour."""

    @pytest.mark.asyncio
    async def test_update_and_set_comfort(self):
        written: list = []
        writer = AsyncMock(side_effect=lambda msg: written.append(msg))
        ctrl = Mock()
        ctrl.send = writer

        module = Module(0x0C, 0x0E, controller=ctrl)
        module._data = {
            "Type": "VMB1TS",
            "TemperatureChannel": "01",
            "CommandToClass": {
                "E7": "TempSensorSettingsRequest",
                "E8": "TempSensorSettingsPart1",
                "E9": "TempSensorSettingsPart2",
                "C6": "TempSensorSettingsPart3",
                "B9": "TempSensorSettingsPart4",
            },
        }
        temp_ch = Temperature(module, 1, "Temperature", False, False, 0x0C)

        await temp_ch.update_settings_part1(
            current_set=20,
            comfort_heating=21,
            day_heating=20,
            night_heating=18,
            antifreeze_heating=5,
            temp_difference=2,
            hysteresis=0.5,
        )
        await temp_ch.update_settings_part2(
            comfort_cooling=24,
            day_cooling=23,
            night_cooling=22,
            safe_cooling=21,
            default_sleep_timer=60,
            autosend_interval=30,
        )
        await temp_ch.update_settings_part3(
            alarm_low=5,
            alarm_high=30,
            cool_lower=8,
            heat_upper=25,
            calibration=0,
            slave_or_zone=0xFF,
            calibration_gain=0,
        )
        await temp_ch.update_settings_part4(
            min_switching_time=1,
            pump_delayed_on=0,
            pump_delayed_off=0,
            alarm_2=0,
            alarm_3=0,
            heat_lower=0,
            cool_upper=0,
        )

        assert temp_ch.get_setting("comfort_heating") == 21.0
        assert temp_ch.get_setting("default_sleep_timer") == 60
        assert temp_ch.get_setting("min_switching_time") == 1

        await temp_ch.set_setting("comfort_heating", 22.5)
        assert isinstance(written[-1], TempSensorSettingsPart1)
        assert written[-1].comfort_heating == 22.5
        assert written[-1].data_to_binary()[2] == 45  # 22.5 * 2

        params = temp_ch.get_config_parameters()
        keys = {param.key for param in params}
        assert keys == {
            "temp_difference",
            "hysteresis",
            "default_sleep_timer",
            "autosend_interval",
        }

        param = next(p for p in params if p.key == "hysteresis")
        assert await param.get_value() == 0.5
        await param.set_value(1.0)
        assert temp_ch.get_setting("hysteresis") == 1.0

    @pytest.mark.asyncio
    async def test_unknown_key(self):
        """Unknown setting keys are rejected."""
        module = Module(0x0C, 0x0E, controller=Mock())
        temp_ch = Temperature(module, 1, "Temperature", False, False, 0x0C)
        with pytest.raises(VelbusConfigError):
            await temp_ch.set_setting("nope", 1)
