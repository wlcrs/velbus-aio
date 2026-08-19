"""Tests for VelbusScanner."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from velbusaio.message import Message
from velbusaio.messages.module_subtype import ModuleSubTypeMessage
from velbusaio.messages.module_type import ModuleTypeMessage
from velbusaio.scanner import Scanner, VelbusScanner


def test_scanner_init() -> None:
    """Test scanner initialization."""
    controller = MagicMock()
    scanner = VelbusScanner(controller, one_address=5)
    assert scanner._one_address == 5
    assert not scanner.scan_complete
    assert Scanner is VelbusScanner


def test_scanner_progress_callback() -> None:
    """Test setting and triggering scan progress callback."""
    controller = MagicMock()
    scanner = VelbusScanner(controller)
    callback = MagicMock()
    scanner.progress_callback = callback
    scanner._report_progress("scanning", "10")
    callback.assert_called_once_with("scanning", "10")


def test_scanner_empty_cache(tmp_path) -> None:
    """Test empty_cache."""
    controller = MagicMock()
    controller.cache_dir = str(tmp_path)
    controller.get_cache_dir.return_value = str(tmp_path)
    scanner = VelbusScanner(controller)
    assert scanner.empty_cache() is True

    (tmp_path / "1.json").write_text("{}")
    assert scanner.empty_cache() is False


def test_handle_module_type_response() -> None:
    """Test handling module type response."""
    controller = MagicMock()
    scanner = VelbusScanner(controller)

    # When no scan is in progress, should log warning and not fail
    msg = Message(address=10, data=b"\xFF\x01")
    scanner.on_message(msg)

    # When scan is in progress
    scanner._scan_found_addresses = {}
    type_msg = ModuleTypeMessage(address=10)
    type_msg.module_type = 0x01
    scanner.on_message(type_msg)
    assert scanner._scan_found_addresses[10] is type_msg


def test_handle_module_subtype_response() -> None:
    """Test handling module subtype response."""
    controller = MagicMock()
    mock_module = MagicMock()
    controller.get_module.return_value = None

    scanner = VelbusScanner(controller)
    # Subtype response before module registered
    subtype_msg = Message(
        address=20,
        data=b"\xB0\x00\x00\x00\x21\x22\x23\x24",
    )
    scanner.on_message(subtype_msg)
    assert scanner._scan_sub_addresses[20] == {1: 0x21, 2: 0x22, 3: 0x23, 4: 0x24}

    # When module already registered
    controller.get_module.return_value = mock_module
    subtype_msg_2 = Message(
        address=20,
        data=b"\xA7\x00\x00\x00\x25\xFF\xFF\xFF",
    )
    scanner.on_message(subtype_msg_2)
    controller.add_submodules.assert_called_once_with(
        mock_module,
        {5: 0x25, 6: 0xFF, 7: 0xFF, 8: 0xFF},
    )


@pytest.mark.asyncio
async def test_scan_flow(tmp_path) -> None:
    """Test scan execution flow."""
    controller = MagicMock()
    controller.cache_dir = str(tmp_path)
    controller.get_cache_dir.return_value = str(tmp_path)
    controller.wait_on_all_messages_sent_async = AsyncMock()
    controller.sendTypeRequestMessage = AsyncMock()
    controller.register_module = MagicMock()
    controller._on_modules_loaded = AsyncMock()
    controller.save_module_cache = AsyncMock()
    controller.add_message_listener = MagicMock()
    controller.remove_message_listener = MagicMock()

    scanner = VelbusScanner(controller, one_address=1)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await scanner.scan()

    assert scanner.scan_complete is True
    controller.add_message_listener.assert_called_once_with(scanner.on_message)
    controller.remove_message_listener.assert_called_once_with(scanner.on_message)
    controller.sendTypeRequestMessage.assert_called_once_with(1)
