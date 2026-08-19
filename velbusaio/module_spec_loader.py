"""Hardware module spec loader and build compatibility checking for Velbus modules."""

# ruff: noqa: PLR0917

from __future__ import annotations

import importlib.resources
import json
import logging
from typing import Any

import anyio

from velbusaio.helpers import h2


def format_build(build_year: int | None, build_week: int | None) -> str | None:
    """Return the firmware build as "YYWW", or None when unknown."""
    if build_year is None or build_week is None:
        return None
    return f"{build_year:02d}{build_week:02d}"


def check_memory_map_outdated(
    address: int,
    module_type: int,
    build_year: int | None,
    build_week: int | None,
    spec_data: dict[str, Any],
    log: logging.Logger,
) -> bool:
    """Determine whether the module firmware predates its spec's memory map."""
    expected = spec_data.get("MemoryMapBuild")
    reported = format_build(build_year, build_week)
    if expected is None or reported is None:
        return False

    if len(reported) != len(expected):
        log.debug("Cannot compare build %s to %s", reported, expected)
        return False

    if reported >= expected:
        return False

    log.warning(
        "Module %s (%s) reports build %s, but the module spec describes the memory map from build %s onwards. Memory addresses may be wrong; names and action tables read from this module can be incorrect, so writing to its memory is refused.",
        address,
        h2(module_type),
        reported,
        expected,
    )
    return True


async def load_module_spec(module_type: int, log: logging.Logger) -> dict[str, Any]:
    """Load and merge global.json and module-specific spec JSON."""
    global_data: dict[str, Any] = {}
    data: dict[str, Any] = {}

    try:
        with importlib.resources.path("velbusaio", "module_spec/global.json") as fspath:
            async with await anyio.open_file(fspath) as global_file:
                global_data = json.loads(await global_file.read())
        log.debug("Global module spec loaded")
    except FileNotFoundError:
        log.debug("No global module spec found")

    try:
        with importlib.resources.path(
            "velbusaio", f"module_spec/{h2(module_type)}.json"
        ) as fspath:
            async with await anyio.open_file(fspath) as protocol_file:
                data = json.loads(await protocol_file.read())
        log.debug("Module spec %s loaded", h2(module_type))
    except FileNotFoundError:
        log.warning("No module spec for %s", h2(module_type))

    # Merge global data into module data (module-specific takes precedence)
    for key, value in global_data.items():
        if key not in data:
            data[key] = value
        elif isinstance(value, dict) and isinstance(data[key], dict):
            # Deep merge for nested dictionaries
            data[key] = {**value, **data[key]}

    return data
