"""Tests for Cover domain (Blind and message handlers)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from velbusaio.domains.cover import Blind, BlindState
from velbusaio.messages.blind_status import (
    BlindStatusMessage,
    BlindStatusNg20Message,
    BlindStatusNgMessage,
)
from velbusaio.module import Module


@pytest.mark.asyncio
async def test_cover_domain_single_status():
    """Test routing of single-channel blind status."""
    module = Module(1, 0x1B)
    writer = AsyncMock()

    blind = Blind(module, 1, "Blind 1", False, True, writer, 1)
    module._channels[1] = blind

    msg = BlindStatusNgMessage(1)
    msg.channel = 1
    msg.status = 0x01  # opening
    msg.position = 50

    await module.dispatch_message(msg)

    assert blind.state == BlindState.OPENING
    assert blind.position == 50
    assert blind.is_opening() is True


@pytest.mark.asyncio
async def test_cover_domain_ng20():
    """Test routing of dual-channel NG20 blind status."""
    module = Module(1, 0x20)
    writer = AsyncMock()

    blind1 = Blind(module, 1, "Blind 1", False, True, writer, 1)
    blind2 = Blind(module, 2, "Blind 2", False, True, writer, 1)
    module._channels[1] = blind1
    module._channels[2] = blind2

    msg = BlindStatusNg20Message(1)
    msg.channel = [1, 2]
    msg.status = [0x01, 0x02]
    msg.position = [10, 90]

    await module.dispatch_message(msg)

    assert blind1.state == BlindState.OPENING
    assert blind1.position == 10
    assert blind2.state == BlindState.CLOSING
    assert blind2.position == 90
