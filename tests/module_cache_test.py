"""Tests for Module._get_cache handling of empty and malformed cache files.

Regression test for https://github.com/cereal2nd/velbus-aio/issues/140
(crash on empty module cache file).
"""

import asyncio
import json
import logging
import pathlib

import pytest

from unittest.mock import Mock

from velbusaio.module import Module
from velbusaio.module_spec import ModuleSpec

VMBGP4 = 0x20


def _make_module(cache_dir: pathlib.Path) -> Module:
    ctrl = Mock()
    ctrl.cache_dir = str(cache_dir)
    ctrl.get_cache_dir.return_value = str(cache_dir)
    module = Module(0x01, VMBGP4, controller=ctrl)
    module._log = logging.getLogger("velbus-module")
    return module


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        "",  # empty file
        "   \n  ",  # whitespace only
        "garbage",  # invalid json
        "null",  # valid json, but not a mapping
        "[]",  # valid json list
        "42",  # valid json number
    ],
)
async def test_get_cache_invalid_returns_empty_and_removes_file(tmp_path, content):
    from velbusaio.module_cache import read_cache

    log = logging.getLogger("velbus-cache")
    cfile = tmp_path / "1.json"
    cfile.write_text(content)

    cache = await read_cache(str(tmp_path), 1, log)

    assert cache == {}
    # corrupt/unusable cache files are removed so they are treated as absent
    assert not cfile.exists()


@pytest.mark.asyncio
async def test_get_cache_missing_file_returns_empty(tmp_path):
    from velbusaio.module_cache import read_cache

    log = logging.getLogger("velbus-cache")
    cache = await read_cache(str(tmp_path), 1, log)

    assert cache == {}


@pytest.mark.asyncio
async def test_get_cache_valid_dict_is_preserved(tmp_path):
    from velbusaio.module_cache import read_cache

    log = logging.getLogger("velbus-cache")
    cfile = tmp_path / "1.json"
    cfile.write_text('{"name": "kitchen", "channels": {}}')

    cache = await read_cache(str(tmp_path), 1, log)

    assert cache == {"name": "kitchen", "channels": {}}
    assert cfile.exists()


@pytest.mark.asyncio
async def test_to_cache_name_falls_back_to_type_name(tmp_path):
    """A module without a programmed name caches its type name, not ''."""
    from velbusaio.module_cache import build_cache_dict

    module = _make_module(tmp_path)
    module.spec = ModuleSpec(type_name="VMBDALI-20")
    # _name is still the initial value (no name was ever assembled)
    assert not isinstance(module._name, str)

    cache = build_cache_dict(module)

    assert cache["name"] == "VMBDALI-20"


@pytest.mark.asyncio
async def test_save_cache_persists_unloaded_module(tmp_path):
    """A found module gets a valid cache file."""
    from velbusaio.module_cache import save_module_cache

    module = _make_module(tmp_path)
    module.spec = ModuleSpec(type_name="VMBDALI-20")
    cfile = tmp_path / "1.json"
    assert not cfile.exists()

    await save_module_cache(str(tmp_path), module)

    assert cfile.exists()
    data = json.loads(cfile.read_text())
    assert data["name"] == "VMBDALI-20"
    assert "channels" in data


@pytest.mark.asyncio
async def test_concurrent_cache_writes_leave_valid_json(tmp_path):
    """Concurrent save_module_cache() calls must never leave a corrupt cache file."""
    from velbusaio.module_cache import build_cache_dict, save_module_cache

    module = _make_module(tmp_path)
    cfile = tmp_path / "1.json"

    await asyncio.gather(*(save_module_cache(str(tmp_path), module) for _ in range(50)))

    # File is always valid JSON with no trailing junk
    content = cfile.read_text()
    parsed = json.loads(content)
    assert isinstance(parsed, dict)
    assert parsed == json.loads(json.dumps(build_cache_dict(module)))
    # No leftover temp files
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.asyncio
async def test_load_module_from_cache_constructs_module(tmp_path):
    """load_module_from_cache instantiates and populates a Module."""
    from velbusaio.module_cache import load_module_from_cache, save_module_cache

    ctrl = Mock()
    ctrl.cache_dir = str(tmp_path)
    ctrl.get_cache_dir.return_value = str(tmp_path)
    module = _make_module(tmp_path)
    module.spec = ModuleSpec(type_name="VMBGP4")
    module.name = "Living Room"
    await save_module_cache(str(tmp_path), module)

    loaded_mod = await load_module_from_cache(str(tmp_path), 1, controller=ctrl)
    assert loaded_mod is not None
    assert loaded_mod.name == "Living Room"
