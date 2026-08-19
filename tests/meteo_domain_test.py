"""Tests for Meteo domain message routing."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from velbusaio.domains.input import Sensor
from velbusaio.messages.raw import MeteoRawMessage
from velbusaio.module import Module


@pytest.mark.asyncio
async def test_meteo_domain_raw_message():
    """Test routing MeteoRawMessage to rain, light, and wind sensor channels."""
    module = Module(1, 0x18)
    writer = AsyncMock()

    rain = Sensor(module, 11, "Rain", False, True, writer, 1)
    light = Sensor(module, 12, "Light", False, True, writer, 1)
    wind = Sensor(module, 13, "Wind", False, True, writer, 1)
    module._channels[11] = rain
    module._channels[12] = light
    module._channels[13] = wind

    msg = MeteoRawMessage(1)
    msg.rain = 1.2
    msg.light = 450.0
    msg.wind = 5.6

    await module.dispatch_message(msg)

    assert rain.get_state() == 1.2
    assert light.get_state() == 450.0
    assert light.get_unit() == "lx"
    assert wind.get_state() == 5.6
    assert wind.get_unit() == "m/s"
