#!/usr/bin/env python
import pytest

import velbusaio.command_registry
from velbusaio.command_registry import CommandRegistry, register_command


@pytest.fixture()
def own_command_registry():
    """
    Ensure a clean, empty commandRegistry; even when modules are loaded as part of other tests
    """
    orig_command_registry = velbusaio.command_registry.commandRegistry
    velbusaio.command_registry.commandRegistry = CommandRegistry({})
    yield
    velbusaio.command_registry.commandRegistry = orig_command_registry


def test_defaults(own_command_registry):
    # insert some data
    register_command(1, "testclass")
    register_command(2, "testclass2")
    register_command(3, "testclass3")

    # check if double registration is raised
    with pytest.raises(Exception, match=r"double registration in command registry"):
        register_command(1, "testclass")
        register_command(2, "testclass")
        register_command(3, "testclass")

    # check if invalid command id
    with pytest.raises(ValueError, match=r"Command_value should be >=0 and <=255"):
        register_command(0, "testclass")
        register_command(256, "testclass")
