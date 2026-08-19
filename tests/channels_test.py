from unittest.mock import AsyncMock, Mock

from velbusaio.channels import Channel
from velbusaio.command_registry import commandRegistry
from velbusaio.messages.cover_up import CoverUpMessage, CoverUpMessage2
from velbusaio.messages.switch_relay_on import (
    SwitchRelayOnMessage,
    SwitchRelayOnMessage20,
)
from velbusaio.module import Module


def test_channel_set_name_char():
    channel = Channel(None, None, "placeholder", False, False, None)
    name = "FooBar"
    for pos in range(16):
        ch = ord(name[pos]) if pos < len(name) else 0xFF
        channel.set_name_char(pos, ch)
    assert channel.name == "FooBar\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff"


def test_module_create_message_polymorphism():
    """Test Module.create_message resolves module-specific subclasses from specs."""
    commandRegistry.register_module_commands(
        0x26, {"02": "SwitchRelayOnMessage20"}
    )
    commandRegistry.register_module_commands(0x03, {"05": "CoverUpMessage2"})

    ctrl = Mock()
    # VMB4RY (type 0x08) -> SwitchRelayOnMessage
    mod_vmb4ry = Module(0x01, 0x08, controller=ctrl)
    msg_ry = mod_vmb4ry.create_message(SwitchRelayOnMessage)
    assert type(msg_ry) is SwitchRelayOnMessage

    # VMB4RYLD-20 (type 0x26) -> SwitchRelayOnMessage20
    mod_vmb4ryld20 = Module(0x01, 0x26, controller=ctrl)
    msg_20 = mod_vmb4ryld20.create_message(SwitchRelayOnMessage)
    assert type(msg_20) is SwitchRelayOnMessage20
    assert isinstance(msg_20, SwitchRelayOnMessage)

    # Legacy VMB1BL (type 0x03) -> CoverUpMessage2
    mod_vmb1bl = Module(0x01, 0x03, controller=ctrl)
    msg_bl = mod_vmb1bl.create_message(CoverUpMessage)
    assert type(msg_bl) is CoverUpMessage2
    assert isinstance(msg_bl, CoverUpMessage)


def test_channel_create_message_delegation():
    """Test Channel.create_message delegates to Module.create_message with address."""
    commandRegistry.register_module_commands(
        0x26, {"02": "SwitchRelayOnMessage20"}
    )
    mod = Module(0x05, 0x26, controller=Mock())
    channel = Channel(mod, 1, "Relay", False, False, 0x05)
    msg = channel.create_message(SwitchRelayOnMessage)
    assert type(msg) is SwitchRelayOnMessage20
    assert msg.address == 0x05
