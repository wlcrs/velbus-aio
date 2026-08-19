"""Module bus loader for discovering and initializing hardware modules from the bus."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from velbusaio.module import Module

if TYPE_CHECKING:
    from velbusaio.controller import Controller


async def load_module_from_bus(
    address: int,
    module_type: int,
    *,
    controller: Controller,
    serial: int | str | None = None,
    memorymap: int | None = None,
    build_year: int | None = None,
    build_week: int | None = None,
    log: logging.Logger | None = None,
) -> Module:
    """Instantiate a module, interrogate the bus, and return the initialized module."""
    module = Module.factory(
        address,
        module_type,
        controller=controller,
        serial=serial,
        memorymap=memorymap,
        build_year=build_year,
        build_week=build_week,
    )

    await module._request_memory()  # noqa: SLF001
    await module._request_subaddresses()  # noqa: SLF001
    await module._request_channel_name()  # noqa: SLF001
    await module._request_module_status()  # noqa: SLF001

    return module
