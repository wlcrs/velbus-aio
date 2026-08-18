"""Unit tests for the request/simple command message classes."""

from __future__ import annotations

import pytest

from velbusaio.const import PRIORITY_HIGH, PRIORITY_LOW
from velbusaio.message import ParserError
from velbusaio.messages.bus_active import BusActiveMessage
from velbusaio.messages.bus_error_counter_status_request import (
    BusErrorStatusRequestMessage,
)
from velbusaio.messages.bus_off import BusOffMessage
from velbusaio.messages.channel_name_request import (
    ChannelNameRequestMessage,
    ChannelNameRequestMessage2,
    ChannelNameRequestMessage3,
)
from velbusaio.messages.counter_status_request import CounterStatusRequestMessage
from velbusaio.messages.interface_status_request import InterfaceStatusRequestMessage
from velbusaio.messages.light_value_request import LightValueRequest
from velbusaio.messages.memory_dump_request import MemoryDumpRequestMessage
from velbusaio.messages.module_status_request import ModuleStatusRequestMessage
from velbusaio.messages.module_type_request import ModuleTypeRequestMessage
from velbusaio.messages.realtime_clock_status_request import RealtimeClockStatusRequest
from velbusaio.messages.receive_buffer_full import ReceiveBufferFullMessage
from velbusaio.messages.receive_ready import ReceiveReadyMessage
from velbusaio.messages.sensor_temp_request import (
    TEMP_AUTOSEND_DISABLED,
    TEMP_AUTOSEND_ON_CHANGE,
    SensorTempRequest,
)
from velbusaio.messages.temp_sensor_settings_part1 import TempSensorSettingsPart1
from velbusaio.messages.temp_sensor_settings_part2 import TempSensorSettingsPart2
from velbusaio.messages.temp_sensor_settings_part3 import TempSensorSettingsPart3
from velbusaio.messages.temp_sensor_settings_part4 import TempSensorSettingsPart4
from velbusaio.messages.temp_sensor_settings_request import TempSensorSettingsRequest


class TestBusActiveMessage:
    """Tests for BusActiveMessage."""

    def test_default_high_priority(self):
        """Test Default high priority."""
        assert BusActiveMessage(0x01).priority == PRIORITY_HIGH

    def test_populate(self):
        """Test Populate."""
        msg = BusActiveMessage.from_bytes(
            bytes([]), address=0x01, priority=PRIORITY_HIGH, rtr=False
        )
        assert msg.address == 0x01

    def test_data_to_binary(self):
        """Test Data to binary."""
        assert BusActiveMessage().data_to_binary() == bytes([0x0A])


class TestBusOffMessage:
    """Tests for BusOffMessage."""

    def test_populate(self):
        """Test Populate."""
        msg = BusOffMessage.from_bytes(
            bytes([]), address=0x01, priority=PRIORITY_LOW, rtr=False
        )
        assert msg.address == 0x01

    def test_data_to_binary(self):
        """Test Data to binary."""
        assert BusOffMessage().data_to_binary() == bytes([0x09])


class TestBusErrorStatusRequestMessage:
    """Tests for BusErrorStatusRequestMessage."""

    def test_data_to_binary(self):
        """Test Data to binary."""
        assert BusErrorStatusRequestMessage().data_to_binary() == bytes([0xD9])


class TestInterfaceStatusRequestMessage:
    """Tests for InterfaceStatusRequestMessage."""

    def test_data_to_binary(self):
        """Test Data to binary."""
        assert InterfaceStatusRequestMessage().data_to_binary() == bytes([0x0E])

    def test_populate_rejects_data(self):
        """Test Populate rejects data."""
        with pytest.raises(ParserError):
            InterfaceStatusRequestMessage.from_bytes(
                bytes([0x01]), address=0x01, priority=PRIORITY_LOW, rtr=False
            )


class TestMemoryDumpRequestMessage:
    """Tests for MemoryDumpRequestMessage."""

    def test_data_to_binary(self):
        """Test Data to binary."""
        assert MemoryDumpRequestMessage().data_to_binary() == bytes([0xCB])


class TestRealtimeClockStatusRequest:
    """Tests for RealtimeClockStatusRequest."""

    def test_data_to_binary(self):
        """Test Data to binary."""
        assert RealtimeClockStatusRequest().data_to_binary() == bytes([0xD7])


class TestSensorTempRequest:
    """Tests for SensorTempRequest."""

    def test_data_to_binary(self):
        """Test Data to binary."""
        assert SensorTempRequest().data_to_binary() == bytes([0xE5])

    def test_data_to_binary_disabled(self):
        """Test autosend disabled ('never')."""
        msg = SensorTempRequest(0x10, TEMP_AUTOSEND_DISABLED)
        assert msg.data_to_binary() == bytes([0xE5, 0x01])

    def test_data_to_binary_on_change(self):
        """Test autosend on temperature change."""
        msg = SensorTempRequest(0x10, TEMP_AUTOSEND_ON_CHANGE)
        assert msg.data_to_binary() == bytes([0xE5, 0x05])

    def test_data_to_binary_fixed_interval(self):
        """Test autosend with a fixed interval in seconds."""
        msg = SensorTempRequest(0x10, 60)
        assert msg.data_to_binary() == bytes([0xE5, 60])


class TestLightValueRequest:
    """Tests for LightValueRequest."""

    def test_data_to_binary(self):
        """Test Data to binary."""
        assert LightValueRequest().data_to_binary() == bytes([0xAA])


class TestReceiveBufferFullMessage:
    """Tests for ReceiveBufferFullMessage."""

    def test_default_high_priority(self):
        """Test Default high priority."""
        assert ReceiveBufferFullMessage(0x01).priority == PRIORITY_HIGH

    def test_data_to_binary(self):
        """Test Data to binary."""
        assert ReceiveBufferFullMessage().data_to_binary() == bytes([0x0B])


class TestReceiveReadyMessage:
    """Tests for ReceiveReadyMessage."""

    def test_data_to_binary(self):
        """Test Data to binary."""
        assert ReceiveReadyMessage().data_to_binary() == bytes([0x0C])


class TestTempSensorSettingsRequest:
    """Tests for TempSensorSettingsRequest."""

    def test_data_to_binary(self):
        """Test Data to binary."""
        assert TempSensorSettingsRequest().data_to_binary() == bytes([0xE7])


class TestTempSensorSettingsParts:
    """Tests for TempSensorSettingsPart1..4."""

    def test_part1_roundtrip(self):
        """Test Part1 populate / data_to_binary."""
        msg = TempSensorSettingsPart1.from_bytes(
            bytes([40, 42, 40, 36, 10, 4, 1]),
            address=0x01,
            priority=PRIORITY_LOW,
            rtr=False,
        )
        assert msg.current_set == 20.0
        assert msg.comfort_heating == 21.0
        assert msg.day_heating == 20.0
        assert msg.night_heating == 18.0
        assert msg.antifreeze_heating == 5.0
        assert msg.temp_difference == 2.0
        assert msg.hysteresis == 0.5
        assert msg.data_to_binary() == bytes([0xE8, 40, 42, 40, 36, 10, 4, 1])

    def test_part2_roundtrip(self):
        """Test Part2 populate / data_to_binary."""
        msg = TempSensorSettingsPart2.from_bytes(
            bytes([44, 42, 40, 38, 0x00, 0x3C, 30]),
            address=0x01,
            priority=PRIORITY_LOW,
            rtr=False,
        )
        assert msg.comfort_cooling == 22.0
        assert msg.default_sleep_timer == 60
        assert msg.autosend_interval == 30
        assert msg.data_to_binary() == bytes([0xE9, 44, 42, 40, 38, 0x00, 0x3C, 30])

    def test_part3_classic_and_gp(self):
        """Test Part3 layouts."""
        classic = TempSensorSettingsPart3.from_bytes(
            bytes([10, 60, 16, 50, 0, 0xFF]),
            address=0x01,
            priority=PRIORITY_LOW,
            rtr=False,
        )
        classic.layout = "classic"
        assert classic.alarm_low == 5.0
        assert classic.alarm_high == 30.0
        assert classic.slave_or_zone == 0xFF
        assert classic.data_to_binary() == bytes([0xC6, 10, 60, 16, 50, 0, 0xFF])

        gp = TempSensorSettingsPart3.from_bytes(
            bytes([10, 60, 16, 50, 0, 1, 2]),
            address=0x01,
            priority=PRIORITY_LOW,
            rtr=False,
        )
        gp.layout = "gp"
        assert gp.calibration_gain == 2
        assert gp.data_to_binary() == bytes([0xC6, 10, 60, 16, 50, 0, 1, 2])

    def test_part4_classic_and_gp(self):
        """Test Part4 layouts."""
        classic = TempSensorSettingsPart4.from_bytes(
            bytes([5]), address=0x01, priority=PRIORITY_LOW, rtr=False
        )
        classic.layout = "classic"
        assert classic.min_switching_time == 5
        assert classic.data_to_binary() == bytes([0xB9, 5])

        gp = TempSensorSettingsPart4.from_bytes(
            bytes([5, 10, 20, 12, 14, 16, 40]),
            address=0x01,
            priority=PRIORITY_LOW,
            rtr=False,
        )
        gp.layout = "gp"
        assert gp.pump_delayed_on == 10
        assert gp.alarm_2 == 6.0
        assert gp.cool_upper == 20.0
        assert gp.data_to_binary() == bytes([0xB9, 5, 10, 20, 12, 14, 16, 40])


class TestModuleStatusRequestMessage:
    """Tests for ModuleStatusRequestMessage."""

    def test_populate(self):
        """Test Populate."""
        msg = ModuleStatusRequestMessage.from_bytes(
            bytes([0x03]), address=0x01, priority=PRIORITY_LOW, rtr=False
        )
        assert msg.channels == [1, 2]

    def test_data_to_binary_list(self):
        """Test Data to binary list."""
        msg = ModuleStatusRequestMessage()
        msg.channels = [1, 2]
        assert msg.data_to_binary() == bytes([0xFA, 0x03])

    def test_data_to_binary_str(self):
        """Test Data to binary str."""
        msg = ModuleStatusRequestMessage()
        msg.channels = "FF"
        assert msg.data_to_binary() == bytes([0xFA, 0xFF])


class TestModuleTypeRequestMessage:
    """Tests for ModuleTypeRequestMessage."""

    def test_defaults_rtr(self):
        """Test Defaults rtr."""
        msg = ModuleTypeRequestMessage(0x01)
        assert msg.rtr is True
        assert msg.priority == PRIORITY_LOW

    def test_populate(self):
        """Test Populate."""
        msg = ModuleTypeRequestMessage.from_bytes(
            bytes([]), address=0x01, priority=PRIORITY_LOW, rtr=True
        )
        assert msg.address == 0x01

    def test_data_to_binary(self):
        """Test Data to binary."""
        assert ModuleTypeRequestMessage().data_to_binary() == bytes([])


class TestChannelNameRequestMessage:
    """Tests for ChannelNameRequestMessage."""

    def test_populate(self):
        """Test Populate."""
        msg = ChannelNameRequestMessage.from_bytes(
            bytes([0x03]), address=0x01, priority=PRIORITY_LOW, rtr=False
        )
        assert msg.channels == [1, 2]

    def test_data_to_binary_list(self):
        """Test Data to binary list."""
        msg = ChannelNameRequestMessage()
        msg.channels = [1, 2]
        assert msg.data_to_binary() == bytes([0xEF, 0x03])

    def test_data_to_binary_non_list(self):
        """Test Data to binary non list."""
        msg = ChannelNameRequestMessage()
        msg.channels = "all"
        assert msg.data_to_binary() == bytes([0xEF, 0xFF])


class TestChannelNameRequestMessage2:
    """Tests for ChannelNameRequestMessage2 (VMB2BL)."""

    def test_populate(self):
        """Test Populate."""
        msg = ChannelNameRequestMessage2.from_bytes(
            bytes([0x06]), address=0x01, priority=PRIORITY_LOW, rtr=False
        )
        assert msg.channels == [1, 2]

    def test_data_to_binary(self):
        """Test Data to binary."""
        msg = ChannelNameRequestMessage2()
        msg.channels = [1, 2]
        assert msg.data_to_binary() == bytes([0xEF, 0x0F])


class TestChannelNameRequestMessage3:
    """Tests for ChannelNameRequestMessage3 (VMBDALI)."""

    def test_populate(self):
        """Test Populate."""
        msg = ChannelNameRequestMessage3.from_bytes(
            bytes([0x05]), address=0x01, priority=PRIORITY_LOW, rtr=False
        )
        assert msg.channels == 5

    def test_data_to_binary(self):
        """Test Data to binary."""
        msg = ChannelNameRequestMessage3()
        msg.channels = 5
        assert msg.data_to_binary() == bytes([0xEF, 5])


class TestCounterStatusRequestMessage:
    """Tests for CounterStatusRequestMessage."""

    def test_populate(self):
        """Test Populate."""
        msg = CounterStatusRequestMessage.from_bytes(
            bytes([0x00, 0x00]), address=0x01, priority=PRIORITY_LOW, rtr=False
        )
        assert msg.address == 0x01

    def test_data_to_binary(self):
        """Test Data to binary."""
        msg = CounterStatusRequestMessage()
        msg.channels = [1]
        assert msg.data_to_binary() == bytes([0xBD, 0x01, 0x00])
