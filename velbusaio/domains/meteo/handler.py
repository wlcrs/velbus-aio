"""Meteo domain message handlers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from velbusaio.domains.input.channel import Sensor
from velbusaio.message_router import register_handler
from velbusaio.messages.raw import MeteoRawMessage

if TYPE_CHECKING:
    from velbusaio.module import Module

_LOG = logging.getLogger("velbus-meteo")


@register_handler
async def handle_meteo_raw(module: Module, message: MeteoRawMessage) -> None:
    """Route MeteoRawMessage across channels 11 (rain), 12 (light), 13 (wind)."""
    sensors = {
        num: ch for num, ch in module.channels.items() if isinstance(ch, Sensor)
    }
    if rain_ch := sensors.get(11):
        await rain_ch.update_raw(message.rain)
    else:
        _LOG.warning(
            f"Received meteo rain data for missing channel 11 on module {module.address}"
        )

    if light_ch := sensors.get(12):
        await light_ch.update_raw(message.light, "lx")
    else:
        _LOG.warning(
            f"Received meteo light data for missing channel 12 on module {module.address}"
        )

    if wind_ch := sensors.get(13):
        await wind_ch.update_raw(message.wind, "m/s")
    else:
        _LOG.warning(
            f"Received meteo wind data for missing channel 13 on module {module.address}"
        )
