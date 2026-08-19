"""Tests for Power domain property routing."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from velbusaio.messages.bus_error_counter_status import BusErrorCounterStatusMessage
from velbusaio.messages.psu_load import PsuLoadMessage
from velbusaio.messages.psu_values import PsuValuesMessage
from velbusaio.module import Module
from velbusaio.properties import (
    BusErrorOff,
    BusErrorRx,
    BusErrorTx,
    PSUCurrent,
    PSULoad,
    PSUPower,
    PSUVoltage,
)


@pytest.mark.asyncio
async def test_power_domain_psu_values():
    """Test PSU volt/amp/watt properties routing."""
    module = Module(1, 0x30)
    writer = AsyncMock()
    v1 = PSUVoltage(module, "psu_1_volt", writer)
    c1 = PSUCurrent(module, "psu_1_amp", writer)
    p1 = PSUPower(module, "psu_1_watt", writer)

    module._properties["psu_1_volt"] = v1
    module._properties["psu_1_amp"] = c1
    module._properties["psu_1_watt"] = p1

    msg = PsuValuesMessage(1)
    msg.channel = 1
    msg.volt = 13.8
    msg.amp = 2.5
    msg.watt = 34.5

    await module.dispatch_message(msg)

    assert v1.get_state() == 13.8
    assert c1.get_state() == 2.5
    assert p1.get_state() == 34.5


@pytest.mark.asyncio
async def test_power_domain_bus_error_counters():
    """Test CAN bus error counter property routing."""
    module = Module(1, 0x30)
    writer = AsyncMock()
    off_prop = BusErrorOff(module, "bus_off", writer)
    rx_prop = BusErrorRx(module, "bus_rx", writer)
    tx_prop = BusErrorTx(module, "bus_tx", writer)

    module._properties["bus_off"] = off_prop
    module._properties["bus_rx"] = rx_prop
    module._properties["bus_tx"] = tx_prop

    msg = BusErrorCounterStatusMessage(1)
    msg.bus_off_counter = 0
    msg.receive_error_counter = 3
    msg.transmit_error_counter = 1

    await module.dispatch_message(msg)

    assert off_prop.get_state() == 0
    assert rx_prop.get_state() == 3
    assert tx_prop.get_state() == 1
