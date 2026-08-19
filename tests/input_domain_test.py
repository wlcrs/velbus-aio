"""Tests for Input domain (Button, ButtonCounter, Sensor, and message handlers)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from velbusaio.domains.input import Button, ButtonCounter, Sensor
from velbusaio.messages.counter_status import CounterStatusMessage
from velbusaio.messages.counter_value import CounterValueMessage
from velbusaio.messages.push_button_status import PushButtonStatusMessage
from velbusaio.messages.raw import SensorRawMessage
from velbusaio.module import Module


@pytest.mark.asyncio
async def test_input_domain_push_button_status(mock_controller):
    """Test push button opened and closed status routing."""
    module = Module(1, 0x08, controller=mock_controller)
    btn1 = Button(module, 1, "Button 1", False, True, 1)
    btn2 = Button(module, 2, "Button 2", False, True, 1)
    module._channels[1] = btn1
    module._channels[2] = btn2

    msg = PushButtonStatusMessage(1)
    msg.closed = [1]
    msg.opened = [2]

    await module.on_message(msg)
    assert btn1.is_closed() is True
    assert btn2.is_closed() is False


@pytest.mark.asyncio
async def test_input_domain_counter(mock_controller):
    """Test counter pulses and power/energy routing."""
    module = Module(1, 0x08, controller=mock_controller)
    counter = ButtonCounter(module, 1, "Counter 1", False, True, 1)
    module._channels[1] = counter

    c_status = CounterStatusMessage(1)
    c_status.channel = 1
    c_status.pulse_units = 1
    c_status.counter = 5000
    c_status.delay = 10
    await module.on_message(c_status)
    assert counter.counter == 5000
    assert counter.pulses == 100

    c_val = CounterValueMessage(1)
    c_val.channel = 1
    c_val.power = 1200.5
    c_val.energy = 45000.0
    await module.on_message(c_val)
    assert counter.power == 1200.5
    assert counter.raw_energy == 45000.0
    assert counter.get_state() == 45000.0


@pytest.mark.asyncio
async def test_input_domain_sensor_raw(mock_controller):
    """Test analog sensor raw value routing."""
    module = Module(1, 0x08, controller=mock_controller)
    sensor = Sensor(module, 1, "Sensor 1", False, True, 1)
    module._channels[1] = sensor

    msg = SensorRawMessage(1)
    msg.sensor = 1
    msg.value = 23.5
    msg.unit = "°C"
    await module.on_message(msg)
    assert sensor.get_state() == 23.5
    assert sensor.get_unit() == "°C"
