"""This test checks if with an incoming module_status message the selected program
is correctly stored into the module.
"""

import pathlib
from unittest.mock import MagicMock

import pytest

from velbusaio.channels import Channel
from velbusaio.const import NO_RTR, PRIORITY_LOW
from velbusaio.controller import Velbus
from velbusaio.helpers import get_cache_dir
from velbusaio.messages.module_status import (
    PROGRAM_SELECTION,
    ModuleStatusGP4PirMessage,
    ModuleStatusMessage2,
    ModuleStatusPirMessage,
)
from velbusaio.module import Module
from velbusaio.properties import LightValue, SelectedProgram

# some modules to test
VMBGP4 = 0x20
VMBGPOD = 0x28
VMBPIRM = 0x2A
VMBGP4PIR = 0x2D
VMBGPOD_2 = 0x3D
VMBGP4PIR_2 = 0x3E
VMBGP4PIR_20 = 0x5F


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module_type",
    [
        VMBGP4,
        VMBGPOD,
        VMBGPOD_2,
        VMBGP4PIR,
        VMBGP4PIR_2,
        VMBGP4PIR_20,
        VMBPIRM,
    ],
)
async def test_module_status_selected_program(module_type):
    module_address = 1
    cache_dir = get_cache_dir()
    pathlib.Path(cache_dir).mkdir(parents=True, exist_ok=True)

    velbus = Velbus("")  # Dummy connection
    m = Module(
        module_address,
        module_type,
        controller=velbus,
    )

    # load the module with dummy channels
    for chan in range(1, 9):
        m.channels[chan] = Channel(None, None, None, False, False, None)
    m.properties["light_value"] = LightValue(m, "Light")
    m.properties["selected_program"] = SelectedProgram(m, "program")

    messages_to_test = [
        ModuleStatusMessage2,
        ModuleStatusGP4PirMessage,
        ModuleStatusPirMessage,
    ]

    # test all message variants that have the selected_program variable
    for message in messages_to_test:
        msg = message(module_address)

        # test all possible program selections
        for program in PROGRAM_SELECTION.keys():
            msg.selected_program = program
            await m.on_message(msg)
            assert (
                m.properties["selected_program"].value
                == PROGRAM_SELECTION[program]
            )

            # Send the select_program message and check if the binary data is ok
            await m.properties["selected_program"].set(
                PROGRAM_SELECTION[program]
            )
            msg_info = await velbus._protocol._send_queue.get()
            assert msg_info.data[1] == program

    # test GP4PIR lightvalue
    light_values = [0, 100, 1023]
    for light_value in light_values:
        databyte1 = (light_value & 0x300) >> 4
        databyte2 = light_value & 0xFF
        msg = ModuleStatusGP4PirMessage.from_bytes(
            bytes([0x00, databyte1, databyte2, 0x00, 0x00, 0x00, 0x00]),
            address=module_address,
            priority=PRIORITY_LOW,
            rtr=NO_RTR,
        )
        await m.on_message(msg)
        assert m.properties["light_value"].value == light_value
