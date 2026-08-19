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
    from velbusaio.module import Module


def build_cache_dict(module: Module) -> dict[str, Any]:
    """Build cache dictionary from module state."""
    d: dict[str, Any] = {
        "name": (
            module._name if isinstance(module._name, str) else module.get_type_name()  # noqa: SLF001
        ),
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
    lock: asyncio.Lock,
    use_cache: bool = True,
) -> None:
    """Atomically write cache dictionary to disk."""
    if not use_cache or not cache_dir:
        return
    cfile = pathlib.Path(f"{cache_dir}/{address}.json")
    data_str = json.dumps(data, indent=4)
    async with lock:
        tmpfile = cfile.with_name(f"{address}.json.{os.getpid()}.tmp")
        async with await anyio.open_file(tmpfile, "w") as fl:
            await fl.write(data_str)
        await anyio.Path(tmpfile).rename(cfile)


async def read_cache(
    cache_dir: str | None, address: int, log: logging.Logger
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
        log.warning(
            "Cache file for module %s is corrupt, removing it",
            address,
        )
        await anyio.Path(cfile).unlink(missing_ok=True)
        return {}
    return cache
