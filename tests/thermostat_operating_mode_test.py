"""This test checks if with an incoming temp_sensor_status message the thermostat operating mode and
sleep_timer values are correctly stored into the module's temperature channel.
"""

import logging
import pathlib
from unittest.mock import MagicMock

import pytest

from velbusaio.channels import Temperature
from velbusaio.controller import Velbus
from velbusaio.helpers import get_cache_dir
from velbusaio.messages.temp_sensor_status import TempSensorStatusMessage
from velbusaio.module import Module

STATUS_MAP = {0: "run", 1: "manual", 2: "sleep", 3: "disable"}




@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_mode, mode_name, sleep_timer",
    [
        (0, "run", 40),
        (1, "manual", 0xFFFF),
        (2, "sleep", 500),
        (3, "disable", 0),
    ],
)
async def test_thermostat_operating_mode(status_mode, mode_name, sleep_timer):
    module_address = 1
    module_type = 40  # VMBGPOD
    cache_dir = get_cache_dir()
    pathlib.Path(cache_dir).mkdir(parents=True, exist_ok=True)

    velbus = MagicMock()

    m = Module(
        module_address,
        module_type,
        cache_dir=get_cache_dir(),
    )
    velbus = Velbus("")  # Dummy connection
    await m.initialize(velbus.send, velbus)
    m._log = logging.getLogger("velbus-module")
    chan = m._translate_channel_name(m._data["TemperatureChannel"])
    m._channels[chan] = Temperature(
        m, chan, None, False, False, velbus.send, module_address
    )

    msg = TempSensorStatusMessage(module_address)
    msg.status_mode = status_mode
    msg.sleep_timer = sleep_timer
    msg.current_temp = 0
    await m.on_message(msg)

    assert m._channels[chan].get_climate_mode() == mode_name
    assert m._channels[chan]._sleep_timer == sleep_timer

    await m._channels[chan].set_climate_mode(mode_name)
    msg_info = await velbus._protocol._send_queue.get()
    check_sleep_timer = (msg_info.data[1] << 8) + msg_info.data[2]
    if mode_name == "run":
        sleep = 0x0
    elif mode_name == "manual":
        sleep = 0xFFFF
    elif mode_name == "sleep":
        sleep = sleep_timer
    else:
        sleep = 0x0

    assert check_sleep_timer == sleep

