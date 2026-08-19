"""Tests for PacketHandler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from velbusaio.command_registry import commandRegistry
from velbusaio.const import PRIORITY_HIGH
from velbusaio.handler import PacketHandler
from velbusaio.message import Message
from velbusaio.messages.module_subtype import ModuleSubTypeMessage
from velbusaio.messages.push_button_status import PushButtonStatusMessage


@pytest.mark.asyncio
async def test_packet_handler_handle_invalid_packets() -> None:
    """Test ignoring out-of-range address or missing command."""
    controller = MagicMock()
    handler = PacketHandler(controller)

    # Address 0 (< 1)
    msg = Message(address=0, data=b"\x01")
    await handler.handle(msg)

    # Address 255 (> 254)
    msg = Message(address=255, data=b"\x01")
    await handler.handle(msg)

    # Empty data (command is None)
    msg = Message(address=1, data=b"")
    await handler.handle(msg)


@pytest.mark.asyncio
async def test_packet_handler_ignores_broadcast_and_ignore_spec() -> None:
    """Test that broadcast and ignore spec messages are ignored."""
    controller = MagicMock()
    handler = PacketHandler(controller)

    # Broadcast command 0x09
    msg = Message(address=10, data=b"\x09")
    await handler.handle(msg)

    # Ignored command 0xC9
    msg = Message(address=10, data=b"\xC9")
    await handler.handle(msg)

    controller.get_module.assert_not_called()


@pytest.mark.asyncio
async def test_packet_handler_routes_module_message() -> None:
    """Test routing known command to module."""
    controller = MagicMock()
    mock_module = MagicMock()
    mock_module.type = 0x01
    mock_module.get_type.return_value = 0x01
    mock_module.on_message = AsyncMock()
    controller.get_module.return_value = mock_module

    commandRegistry.register_command(0x00, PushButtonStatusMessage, "VMB8PB")

    handler = PacketHandler(controller)
    msg = Message(address=10, priority=PRIORITY_HIGH, data=b"\x00\x00\x00\x00")
    await handler.handle(msg)

    mock_module.on_message.assert_called_once()
