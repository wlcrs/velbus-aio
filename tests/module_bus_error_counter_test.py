"""This test checks that an incoming bus error counter message is stored into the
bus error counter properties of the module.
"""

import pathlib

import pytest

from velbusaio.controller import Velbus
from velbusaio.helpers import get_cache_dir
from velbusaio.messages.bus_error_counter_status import BusErrorCounterStatusMessage
from velbusaio.module import Module
from velbusaio.properties import BusErrorOff, BusErrorRx, BusErrorTx

VMBGPOD = 0x28

# distinct values, so a mix-up between the three counters is caught as well
TRANSMIT_ERRORS = 11
RECEIVE_ERRORS = 22
BUS_OFF_COUNT = 33


@pytest.mark.asyncio
async def test_bus_error_counters_are_updated():
    cache_dir = get_cache_dir()
    pathlib.Path(cache_dir).mkdir(parents=True, exist_ok=True)

    velbus = Velbus("")  # Dummy connection
    m = Module(1, VMBGPOD, controller=velbus)

    msg = BusErrorCounterStatusMessage(1)
    msg.transmit_error_counter = TRANSMIT_ERRORS
    msg.receive_error_counter = RECEIVE_ERRORS
    msg.bus_off_counter = BUS_OFF_COUNT

    await m.on_message(msg)

    assert m._properties["bus_error_tx"].value == TRANSMIT_ERRORS
    assert m._properties["bus_error_rx"].value == RECEIVE_ERRORS
    assert m._properties["bus_error_off"].value == BUS_OFF_COUNT
    assert m._properties["bus_error_tx"].get_state() == TRANSMIT_ERRORS
    assert m._properties["bus_error_rx"].get_state() == RECEIVE_ERRORS
    assert m._properties["bus_error_off"].get_state() == BUS_OFF_COUNT
