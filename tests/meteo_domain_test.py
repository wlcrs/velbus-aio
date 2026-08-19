"""Tests for Meteo domain message routing."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from velbusaio.domains.input import Sensor
from velbusaio.messages.raw import MeteoRawMessage
from velbusaio.module import Module


@pytest.mark.asyncio
async def test_meteo_domain_raw_message(mock_controller):
    """Test routing MeteoRawMessage to rain, light, and wind sensor channels."""
    module = Module(1, 0x18, controller=mock_controller)

    rain = Sensor(module, 11, "Rain", False, True, 1)
    light = Sensor(module, 12, "Light", False, True, 1)
    wind = Sensor(module, 13, "Wind", False, True, 1)
    module.channels[11] = rain
    module.channels[12] = light
    module.channels[13] = wind

    msg = MeteoRawMessage(1)
    msg.rain = 1.2
    msg.light = 450.0
    msg.wind = 5.6

    await module.on_message(msg)

    assert rain.get_state() == 1.2
    assert light.get_state() == 450.0
    assert light.get_unit() == "lx"
    assert wind.get_state() == 5.6
    assert wind.get_unit() == "m/s"
