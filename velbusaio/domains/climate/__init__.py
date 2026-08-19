"""Climate domain package for Velbus."""

from __future__ import annotations

from velbusaio.domains.climate.channel import (
    Temperature,
    ThermostatChannel,
    infer_temp_settings_layout,
    module_supports_temp_settings,
)

__all__ = [
    "Temperature",
    "ThermostatChannel",
    "infer_temp_settings_layout",
    "module_supports_temp_settings",
]
