"""Disk cache reader and writer for Velbus hardware modules."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
from typing import TYPE_CHECKING, Any

import anyio

if TYPE_CHECKING:
    from velbusaio.controller import Controller
    from velbusaio.module import Module

_CACHE_LOCK = asyncio.Lock()


def build_cache_dict(module: Module) -> dict[str, Any]:
    """Build cache dictionary from module state."""
    d: dict[str, Any] = {
        "name": (
            module._name if isinstance(module._name, str) else module.get_type_name()  # noqa: SLF001
        ),
        "type": module.get_type(),
        "type_name": module.get_type_name(),
        "serial": module.get_serial(),
        "memory_map_version": module.memory_map_version,
        "build_year": module.build_year,
        "build_week": module.build_week,
        "channels": {},
        "sub_addresses": {},
        "properties": {},
    }
    for chan_num, chan in module._channels.items():  # noqa: SLF001
        d["channels"][chan_num] = chan.to_cache()
    for sub_num, address in module._sub_address.items():  # noqa: SLF001
        d["sub_addresses"][sub_num] = address
    for prop_num, prop in module._properties.items():  # noqa: SLF001
        d["properties"][prop_num] = prop.to_cache()
    return d


async def save_cache(
    cache_dir: str | None,
    address: int,
    data: dict[str, Any],
    lock: asyncio.Lock | None = None,
    use_cache: bool = True,
) -> None:
    """Atomically write cache dictionary to disk."""
    if not use_cache or not cache_dir:
        return
    cfile = pathlib.Path(f"{cache_dir}/{address}.json")
    data_str = json.dumps(data, indent=4)
    file_lock = lock or _CACHE_LOCK
    async with file_lock:
        tmpfile = cfile.with_name(f"{address}.json.{os.getpid()}.tmp")
        async with await anyio.open_file(tmpfile, "w") as fl:
            await fl.write(data_str)
        await anyio.Path(tmpfile).rename(cfile)


async def save_module_cache(
    cache_dir: str | None,
    module: Module,
    lock: asyncio.Lock | None = None,
) -> None:
    """Save a Module's state to disk cache."""
    await save_cache(
        cache_dir,
        module.get_address(),
        build_cache_dict(module),
        lock=lock,
    )


async def read_cache(
    cache_dir: str | None, address: int, log: logging.Logger | None = None
) -> dict[str, Any]:
    """Read cache dictionary from disk."""
    if not cache_dir:
        return {}
    cfile = pathlib.Path(f"{cache_dir}/{address}.json")
    try:
        async with await anyio.open_file(cfile, "r") as fl:
            cache = json.loads(await fl.read())
    except OSError:
        return {}
    except (json.JSONDecodeError, KeyError, ValueError):
        cache = None
    if not isinstance(cache, dict):
        if log:
            log.warning(
                "Cache file for module %s is corrupt, removing it",
                address,
            )
        await anyio.Path(cfile).unlink(missing_ok=True)
        return {}
    return cache


async def load_module_from_cache(
    cache_dir: str | None,
    address: int,
    *,
    controller: Controller,
    module_type: int | None = None,
    log: logging.Logger | None = None,
) -> Module | None:
    """Load and construct a Module instance from disk cache."""
    logger = log or logging.getLogger("velbus-cache")
    cache = await read_cache(cache_dir, address, logger)
    if not cache:
        return None

    resolved_type = cache.get("type") if module_type is None else module_type
    if resolved_type is None:
        return None

    from velbusaio.channels import ButtonCounter
    from velbusaio.module import Module

    module = Module.factory(
        address,
        int(resolved_type),
        controller=controller,
        serial=cache.get("serial"),
        memorymap=cache.get("memory_map_version"),
        build_year=cache.get("build_year"),
        build_week=cache.get("build_week"),
    )

    if "name" in cache and isinstance(cache["name"], str) and cache["name"] != "":
        module._name = cache["name"]  # noqa: SLF001

    if "sub_addresses" in cache:
        for num, addr in cache["sub_addresses"].items():
            module.set_sub_address(int(num), int(addr))

    if "channels" in cache:
        for num, chan in cache["channels"].items():
            chan_num = int(num)
            if chan_num in module._channels:  # noqa: SLF001
                chan_type = chan.get("type")
                existing_chan = module._channels[chan_num]  # noqa: SLF001
                if chan_type in ("CounterChannel", "ButtonCounter") or "Unit" in chan:
                    from velbusaio.channels import CounterChannel  # noqa: PLC0415

                    if not isinstance(existing_chan, CounterChannel):
                        counter = CounterChannel(
                            module=module,
                            num=chan_num,
                            name=chan.get("name", existing_chan.name),
                            nameEditable=getattr(existing_chan, "nameEditable", True),
                            subDevice=chan.get("subdevice", existing_chan.is_sub_device()),
                            address=getattr(existing_chan, "_address", module.get_address()),
                        )
                        module._channels[chan_num] = counter  # noqa: SLF001
                    if "Unit" in chan:
                        module._channels[chan_num].set_unit(chan["Unit"])  # noqa: SLF001
                elif chan_type == "Button":
                    from velbusaio.channels import Button, CounterChannel  # noqa: PLC0415

                    if isinstance(existing_chan, CounterChannel) or not isinstance(existing_chan, Button):
                        btn = Button(
                            module=module,
                            num=chan_num,
                            name=chan.get("name", existing_chan.name),
                            nameEditable=getattr(existing_chan, "nameEditable", True),
                            subDevice=chan.get("subdevice", existing_chan.is_sub_device()),
                            address=getattr(existing_chan, "_address", module.get_address()),
                        )
                        module._channels[chan_num] = btn  # noqa: SLF001
                module._channels[chan_num].name = chan.get("name", "")  # noqa: SLF001

    return module
