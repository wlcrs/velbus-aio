"""Test cases for the Temperature channel class"""

from unittest.mock import Mock, patch

import pytest

from velbusaio.channels import Temperature
from velbusaio.messages.set_temperature import SetTemperatureMessage
from velbusaio.messages.switch_to_comfort import SwitchToComfortMessage
from velbusaio.messages.temp_set_cooling import TempSetCoolingMessage
from velbusaio.messages.temp_set_heating import TempSetHeatingMessage
from velbusaio.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS


class TestTemperature:
    """Test cases for the Temperature channel class."""

    def test_get_categories_thermostat(self, mock_module, mock_writer):
        """Test temperature categories for thermostat."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        temp.thermostat = True
        assert temp.get_categories() == ["sensor", "climate"]

    def test_get_categories_sensor_only(self, mock_module, mock_writer):
        """Test temperature categories for sensor only."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        temp.thermostat = False
        assert temp.get_categories() == ["sensor"]

    def test_get_unit(self, mock_module, mock_writer):
        """Test getting temperature unit."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        assert temp.get_unit() == TEMP_CELSIUS

    @pytest.mark.asyncio
    async def test_get_state(self, mock_module, mock_writer):
        """Test getting temperature state."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        temp.cur = 21.5
        await temp.maybe_status_update()
        assert temp.get_state() == 21.5

    def test_get_sensor_type(self, mock_module, mock_writer):
        """Test getting sensor type."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        assert temp.get_sensor_type() == "temperature"

    def test_temperature_protocol(self, mock_module, mock_writer):
        """Test Temperature channel conforms to Temperature and HasUnit protocols."""
        from velbusaio.protocols import HasUnit, Temperature as TemperatureProto

        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        assert isinstance(temp, TemperatureProto)
        assert isinstance(temp, HasUnit)

    @pytest.mark.asyncio
    async def test_get_max(self, mock_module, mock_writer):
        """Test getting maximum temperature."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        temp.max = 30.5
        await temp.maybe_status_update()
        assert temp.get_max() == 30.5

    def test_get_max_none(self, mock_module, mock_writer):
        """Test getting maximum when not set."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        assert temp.get_max() is None

    @pytest.mark.asyncio
    async def test_get_min(self, mock_module, mock_writer):
        """Test getting minimum temperature."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        temp.min = 15.5
        await temp.maybe_status_update()
        assert temp.get_min() == 15.5

    def test_get_min_none(self, mock_module, mock_writer):
        """Test getting minimum when not set."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        assert temp.get_min() is None

    @pytest.mark.asyncio
    async def test_get_climate_target(self, mock_module, mock_writer):
        """Test getting climate target temperature."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        temp.target = 22.0
        await temp.maybe_status_update()
        assert temp.get_climate_target() == 22.0

    @pytest.mark.asyncio
    async def test_get_climate_preset(self, mock_module, mock_writer):
        """Test getting climate preset mode."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        temp.cmode = "comfort"
        await temp.maybe_status_update()
        assert temp.get_climate_preset() == "comfort"

    @pytest.mark.asyncio
    async def test_get_climate_mode(self, mock_module, mock_writer):
        """Test getting climate operating mode."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        temp.cstatus = "run"
        await temp.maybe_status_update()
        assert temp.get_climate_mode() == "run"

    @pytest.mark.asyncio
    async def test_set_temp(self, mock_module, mock_writer):
        """Test setting temperature."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        await temp.set_temp(22.5)

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, SetTemperatureMessage)
        assert sent_msg.temp == 22.5

    @pytest.mark.asyncio
    async def test_set_preset_comfort(self, mock_module, mock_writer):
        """Test setting preset to comfort mode."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        temp.cstatus = "run"
        await temp.set_preset("comfort")

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, SwitchToComfortMessage)
        assert sent_msg.sleep == 0

    @pytest.mark.asyncio
    async def test_set_climate_mode(self, mock_module, mock_writer):
        """Test setting climate operating mode."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        temp.cmode = "comfort"
        await temp.set_climate_mode("manual")

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, SwitchToComfortMessage)
        assert sent_msg.sleep == 0xFFFF

    @pytest.mark.asyncio
    async def test_set_mode_heat(self, mock_module, mock_writer):
        """Test setting mode to heat."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        await temp.set_mode("heat")

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, TempSetHeatingMessage)

    @pytest.mark.asyncio
    async def test_set_mode_cool(self, mock_module, mock_writer):
        """Test setting mode to cool."""
        temp = Temperature(mock_module, 1, "Temp", False, True, 0x01)
        await temp.set_mode("cool")

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, TempSetCoolingMessage)
