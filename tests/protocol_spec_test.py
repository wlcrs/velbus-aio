"""Tests for protocol message specs (broadcast and ignore)."""

from __future__ import annotations
from unittest.mock import MagicMock
import pytest

from velbusaio.handler import PacketHandler
from velbusaio.protocol_spec import ProtocolMessageSpec
from velbusaio.module_spec_loader import load_broadcast_spec, load_ignore_spec


def test_load_broadcast_spec() -> None:
    """Test loading broadcast specifications."""
    broadcast = load_broadcast_spec()
    assert len(broadcast) > 0
    assert "09" in broadcast
    spec = broadcast["09"]
    assert isinstance(spec, ProtocolMessageSpec)
    assert spec.command == 0x09
    assert spec.command_hex == "09"
    assert spec.name == "COMMAND_BUS_OFF"
    assert spec.priority == "High"
    assert spec.info == "Transmit Bus Off message"
    # Backwards compatibility item access
    assert spec["Name"] == "COMMAND_BUS_OFF"
    assert spec["Prio"] == "High"
    assert spec["Info"] == "Transmit Bus Off message"


def test_load_ignore_spec() -> None:
    """Test loading ignore specifications."""
    ignore = load_ignore_spec()
    assert len(ignore) > 0
    assert "C9" in ignore
    spec = ignore["C9"]
    assert isinstance(spec, ProtocolMessageSpec)
    assert spec.command == 0xC9
    assert spec.command_hex == "C9"
    assert spec.name == "COMMAND_READ_MEMORY_BLOCK"
    assert spec.priority == "Low"
    assert spec["Name"] == "COMMAND_READ_MEMORY_BLOCK"

