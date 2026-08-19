"""Test cases for runtime-checkable Protocols and polymorphic categorization."""

import pytest

from velbusaio.channels import (
    Blind,
    Button,
    ButtonCounter,
    Channel,
    CounterChannel,
    Dimmer,
    Relay,
    Sensor,
    SensorNumber,
    Temperature,
)
from velbusaio.properties import BusErrorTx, MemoText, PSUPower, SelectedProgram
from velbusaio.protocols import (
    Counter,
    Cover,
    Dimmable,
    HasEnergy,
    HasUnit,
    Pressable,
    Switchable,
    Temperature as TemperatureProto,
)


def test_base_channel_protocol_conformance(mock_module):
    """Test that a plain Channel does not conform to specialized protocols."""
    channel = Channel(mock_module, 1, "Channel", False, False, 0x01)
    assert not isinstance(channel, Counter)
    assert not isinstance(channel, TemperatureProto)
    assert not isinstance(channel, HasUnit)
    assert not isinstance(channel, Pressable)
    assert not isinstance(channel, HasEnergy)
    assert not isinstance(channel, Switchable)
    assert not isinstance(channel, Dimmable)
    assert not isinstance(channel, Cover)


def test_button_protocols(mock_module):
    """Test Button protocol conformance."""
    button = Button(mock_module, 1, "Button", False, False, 0x01)
    assert isinstance(button, Pressable)
    assert not isinstance(button, Counter)
    assert not isinstance(button, TemperatureProto)
    assert not isinstance(button, HasUnit)
    assert not isinstance(button, Switchable)
    assert not isinstance(button, Dimmable)
    assert not isinstance(button, Cover)


def test_counter_channel_protocols(mock_module):
    """Test CounterChannel protocol conformance."""
    counter = CounterChannel(mock_module, 1, "Counter", False, False, 0x01)
    assert not isinstance(counter, Pressable)
    assert isinstance(counter, Counter)
    assert isinstance(counter, HasUnit)
    assert isinstance(counter, HasEnergy)
    assert not isinstance(counter, TemperatureProto)
    assert not isinstance(counter, Switchable)
    assert not isinstance(counter, Dimmable)
    assert not isinstance(counter, Cover)


def test_temperature_protocols(mock_module):
    """Test Temperature channel protocol conformance."""
    temp = Temperature(mock_module, 1, "Temp", False, False, 0x01)
    assert isinstance(temp, TemperatureProto)
    assert isinstance(temp, HasUnit)
    assert not isinstance(temp, Counter)
    assert not isinstance(temp, Pressable)
    assert not isinstance(temp, Switchable)
    assert not isinstance(temp, Dimmable)
    assert not isinstance(temp, Cover)


def test_sensor_protocols(mock_module):
    """Test Sensor and SensorNumber protocol conformance."""
    sensor = Sensor(mock_module, 1, "Sensor", False, False, 0x01)
    assert isinstance(sensor, HasUnit)
    assert isinstance(sensor, Pressable)  # inherits from Button

    sensor_num = SensorNumber(mock_module, 1, "SensorNum", False, False, 0x01)
    assert isinstance(sensor_num, HasUnit)
    assert not isinstance(sensor_num, Pressable)


def test_relay_protocols(mock_module):
    """Test Relay channel protocol conformance."""
    relay = Relay(mock_module, 1, "Relay", False, False, 0x01)
    assert isinstance(relay, Switchable)
    assert not isinstance(relay, Counter)
    assert not isinstance(relay, TemperatureProto)
    assert not isinstance(relay, HasUnit)
    assert not isinstance(relay, Pressable)
    assert not isinstance(relay, Cover)


def test_dimmer_protocols(mock_module):
    """Test Dimmer channel protocol conformance."""
    dimmer = Dimmer(mock_module, 1, "Dimmer", False, False, 0x01)
    assert isinstance(dimmer, Dimmable)
    assert not isinstance(dimmer, Counter)
    assert not isinstance(dimmer, TemperatureProto)
    assert not isinstance(dimmer, HasUnit)
    assert not isinstance(dimmer, Cover)


def test_blind_protocols(mock_module):
    """Test Blind channel protocol conformance."""
    blind = Blind(mock_module, 1, "Blind", False, False, 0x01)
    assert isinstance(blind, Cover)
    assert not isinstance(blind, Counter)
    assert not isinstance(blind, TemperatureProto)
    assert not isinstance(blind, HasUnit)
    assert not isinstance(blind, Switchable)
    assert not isinstance(blind, Dimmable)


def test_property_protocols(mock_module):
    """Test Property classes do not conform to channel protocols unless applicable."""
    psu = PSUPower(mock_module, "PSU Power")
    memo = MemoText(mock_module, "Memo")
    prog = SelectedProgram(mock_module, "Program")
    bus_err = BusErrorTx(mock_module, "BusErrorTx")

    for prop in (psu, memo, prog, bus_err):
        assert not isinstance(prop, Counter)
        assert not isinstance(prop, TemperatureProto)
        assert not isinstance(prop, Pressable)
        assert not isinstance(prop, Switchable)
        assert not isinstance(prop, Dimmable)
        assert not isinstance(prop, Cover)
        assert not isinstance(prop, HasEnergy)


@pytest.mark.asyncio
async def test_loader_promotion_during_live_scan(mock_controller):
    """Test that a Button channel is promoted to CounterChannel during the loading phase."""
    from velbusaio.messages.counter_status import CounterStatusMessage
    from velbusaio.module import Module

    module = Module(1, 0x08, controller=mock_controller)
    module._is_loaded = False
    btn = Button(module, 1, "Input 1", False, True, 1)
    module._channels[1] = btn

    # Before message: channel is Button (Pressable, not Counter)
    assert isinstance(module.get_channels()[1], Button)
    assert isinstance(module.get_channels()[1], Pressable)
    assert not isinstance(module.get_channels()[1], Counter)

    # CounterStatusMessage arrives during loading phase
    c_status = CounterStatusMessage(1)
    c_status.channel = 1
    c_status.pulse_units = 1
    c_status.counter = 5000
    c_status.delay = 10
    await module.on_message(c_status)

    # After message: channel is promoted to CounterChannel (Counter, HasUnit, not Pressable)
    channel = module.get_channels()[1]
    assert isinstance(channel, CounterChannel)
    assert isinstance(channel, Counter)
    assert isinstance(channel, HasUnit)
    assert not isinstance(channel, Pressable)
    assert channel.get_categories() == ["sensor"]
    assert channel.counter == 5000


@pytest.mark.asyncio
async def test_loader_detection_from_cache(mock_controller, tmp_path):
    """Test that module cache deserialization accurately restores CounterChannel and Button."""
    from velbusaio.module import Module
    from velbusaio.module_cache import load_module_from_cache, save_module_cache

    module = Module(1, 0x4E, controller=mock_controller)
    counter = CounterChannel(module, 1, "Water Meter", False, True, 1)
    counter.set_unit("L/h")
    btn = Button(module, 2, "Kitchen Switch", False, True, 1)
    module._channels[1] = counter
    module._channels[2] = btn

    await save_module_cache(str(tmp_path), module)

    restored = await load_module_from_cache(
        str(tmp_path), 1, controller=mock_controller
    )
    assert restored is not None
    assert isinstance(restored._channels[1], CounterChannel)
    assert isinstance(restored._channels[1], Counter)
    assert restored._channels[1].get_unit() == "L"
    assert isinstance(restored._channels[2], Button)
    assert isinstance(restored._channels[2], Pressable)
    assert not isinstance(restored._channels[2], Counter)

