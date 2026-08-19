"""Hardware module spec loader and build compatibility checking for Velbus modules."""

from __future__ import annotations

import importlib.resources
import json
import logging
from typing import Any

from velbusaio.helpers import h2
from velbusaio.module_spec import ModuleSpec
from velbusaio.protocol_spec import ProtocolMessageSpec


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
    spec_data: ModuleSpec | dict[str, Any],
    log: logging.Logger,
) -> bool:
    """Determine whether the module firmware predates its spec's memory map."""
    if isinstance(spec_data, ModuleSpec):
        expected = spec_data.memory_map_build
    else:
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



def load_broadcast_spec() -> dict[str, ProtocolMessageSpec]:
    """Load broadcast message specifications."""
    path = importlib.resources.files("velbusaio").joinpath("module_spec/broadcast.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        cmd_hex: ProtocolMessageSpec.from_dict(cmd_hex, spec)
        for cmd_hex, spec in data.items()
    }

broadcast_spec : dict[str, ProtocolMessageSpec]  = load_broadcast_spec()


def load_ignore_spec() -> dict[str, ProtocolMessageSpec]:
    """Load ignored message specifications."""
    path = importlib.resources.files("velbusaio").joinpath("module_spec/ignore.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        cmd_hex: ProtocolMessageSpec.from_dict(cmd_hex, spec)
        for cmd_hex, spec in data.items()
    }
    return _IGNORE_CACHE

ignore_spec : dict[str, ProtocolMessageSpec]  = load_ignore_spec()

_SPEC_CACHE: dict[int, ModuleSpec] = {}


def load_module_spec(
    module_type: int, log: logging.Logger | None = None
) -> ModuleSpec:
    """Load and merge global.json and module-specific spec JSON, returning a ModuleSpec."""
    if module_type in _SPEC_CACHE:
        return _SPEC_CACHE[module_type]

    global_data: dict[str, Any] = {}
    try:
        global_path = importlib.resources.files("velbusaio").joinpath(
            "module_spec/global.json"
        )
        if global_path.is_file():
            global_data = json.loads(global_path.read_text(encoding="utf-8"))
            if log:
                log.debug("Global module spec loaded")
        elif log:
            log.debug("No global module spec found")
    except Exception:
        if log:
            log.debug("No global module spec found")

    data: dict[str, Any] = {}
    try:
        spec_path = importlib.resources.files("velbusaio").joinpath(
            f"module_spec/{h2(module_type)}.json"
        )
        if spec_path.is_file():
            data = json.loads(spec_path.read_text(encoding="utf-8"))
            if log:
                log.debug("Module spec %s loaded", h2(module_type))
        elif log:
            log.warning("No module spec for %s", h2(module_type))
    except Exception:
        if log:
            log.warning("No module spec for %s", h2(module_type))

    # Merge global data into module data (module-specific takes precedence)
    for key, value in global_data.items():
        if key not in data:
            data[key] = value
        elif isinstance(value, dict) and isinstance(data[key], dict):
            # Deep merge for nested dictionaries
            data[key] = {**value, **data[key]}

    spec = ModuleSpec.from_dict(data)
    _SPEC_CACHE[module_type] = spec
    return spec
