"""Tests for Lighting domain (Dimmer, Relay, and message handlers)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from velbusaio.domains.lighting import Dimmer, Relay
from velbusaio.messages.dali_dim_value_status import DimValueStatus
from velbusaio.messages.dimmer_status import DimmerStatusMessage
from velbusaio.messages.relay_status import RelayStatusMessage, RelayStatusMessage3
from velbusaio.module import Module


@pytest.mark.asyncio
async def test_lighting_domain_relay():
    """Test routing of relay messages."""
    module = Module(1, 0x08)
    writer = AsyncMock()

    relay = Relay(module, 1, "Relay 1", False, True, writer, 1)
    module._channels[1] = relay

    msg = RelayStatusMessage(1)
    msg.channel = 1
    msg.status = 0x01  # ON
    msg.disable_inhibit_forced = 0x00

    await module.dispatch_message(msg)
    assert relay.is_on() is True


@pytest.mark.asyncio
async def test_lighting_domain_relay3():
    """Test routing of RelayStatusMessage3 across 4 channels."""
    module = Module(1, 0x08)
    writer = AsyncMock()

    for i in range(1, 5):
        module._channels[i] = Relay(module, i, f"Relay {i}", False, True, writer, 1)

    msg = RelayStatusMessage3(1)
    msg.status_bits = 0b00000101  # channels 1 and 3 ON
    msg.inhibited_bits = 0
    msg.forced_on_bits = 0
    msg.forced_off_bits = 0
    msg.program_disabled_bits = 0

    await module.dispatch_message(msg)

    assert module._channels[1].is_on() is True
    assert module._channels[2].is_on() is False
    assert module._channels[3].is_on() is True
    assert module._channels[4].is_on() is False


@pytest.mark.asyncio
async def test_lighting_domain_dimmer_and_dali():
    """Test routing of Dimmer and DALI dim values."""
    module = Module(1, 0x15)
    writer = AsyncMock()

    dimmer1 = Dimmer(module, 1, "Dimmer 1", False, True, writer, 1)
    dimmer2 = Dimmer(module, 2, "Dimmer 2", False, True, writer, 1)
    module._channels[1] = dimmer1
    module._channels[2] = dimmer2

    msg = DimmerStatusMessage(1)
    msg.channel = 1
    msg.dimmer_state = 80
    await module.dispatch_message(msg)
    assert dimmer1.get_dimmer_state() == 80

    dali_msg = DimValueStatus(1)
    dali_msg.channel = 1
    dali_msg.dim_values = [40, 60]
    await module.dispatch_message(dali_msg)
    assert dimmer1.state == 40
    assert dimmer2.state == 60
