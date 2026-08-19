"""Test cases for the Blind channel class"""

from unittest.mock import Mock, patch

import pytest

from velbusaio.channels import Blind, BlindState
from velbusaio.messages.cover_down import CoverDownMessage
from velbusaio.messages.cover_off import CoverOffMessage
from velbusaio.messages.cover_position import CoverPosMessage
from velbusaio.messages.cover_up import CoverUpMessage


class TestBlind:
    """Test cases for the Blind channel class."""

    def test_get_categories(self, mock_module, mock_writer):
        """Test blind categories."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        assert blind.get_categories() == ["cover"]

    @pytest.mark.asyncio
    async def test_position(self, mock_module, mock_writer):
        """Test blind position attribute."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        blind.position = 50
        await blind.maybe_status_update()
        assert blind.position == 50

    @pytest.mark.asyncio
    async def test_state(self, mock_module, mock_writer):
        """Test blind state attribute and update_status."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        await blind.update_status(0x01, 50)
        assert blind.state == BlindState.OPENING
        assert blind.position == 50

    @pytest.mark.asyncio
    async def test_is_opening(self, mock_module, mock_writer):
        """Test checking if blind is opening."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        blind.state = BlindState.OPENING
        await blind.maybe_status_update()
        assert blind.is_opening()
        assert not blind.is_closing()
        assert not blind.is_stopped()

    @pytest.mark.asyncio
    async def test_is_closing(self, mock_module, mock_writer):
        """Test checking if blind is closing."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        blind.state = BlindState.CLOSING
        await blind.maybe_status_update()
        assert blind.is_closing()
        assert not blind.is_opening()
        assert not blind.is_stopped()

    @pytest.mark.asyncio
    async def test_is_stopped(self, mock_module, mock_writer):
        """Test checking if blind is stopped."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        blind.state = BlindState.STOPPED
        await blind.maybe_status_update()
        assert blind.is_stopped()
        assert not blind.is_opening()
        assert not blind.is_closing()

    @pytest.mark.asyncio
    async def test_is_closed_with_position(self, mock_module, mock_writer):
        """Test checking if blind is closed when position is known."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        blind.position = 100
        await blind.maybe_status_update()
        assert blind.is_closed()

        blind.position = 50
        await blind.maybe_status_update()
        assert not blind.is_closed()

    def test_is_closed_without_position(self, mock_module, mock_writer):
        """Test checking if blind is closed when position is unknown."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        assert blind.is_closed() is None

    @pytest.mark.asyncio
    async def test_is_open_with_position(self, mock_module, mock_writer):
        """Test checking if blind is open when position is known."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        blind.position = 0
        await blind.maybe_status_update()
        assert blind.is_open()

        blind.position = 50
        await blind.maybe_status_update()
        assert not blind.is_open()

    def test_is_open_without_position(self, mock_module, mock_writer):
        """Test checking if blind is open when position is unknown."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        assert blind.is_open() is None

    @pytest.mark.asyncio
    async def test_support_position(self, mock_module, mock_writer):
        """Test checking if position is supported."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        assert not blind.support_position()

        blind.position = 50
        await blind.maybe_status_update()
        assert blind.support_position()

    @pytest.mark.asyncio
    async def test_open(self, mock_module, mock_writer):
        """Test opening blind."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        await blind.open()

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, CoverUpMessage)
        assert sent_msg.channel == 1

    @pytest.mark.asyncio
    async def test_close(self, mock_module, mock_writer):
        """Test closing blind."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        await blind.close()

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, CoverDownMessage)
        assert sent_msg.channel == 1

    @pytest.mark.asyncio
    async def test_stop(self, mock_module, mock_writer):
        """Test stopping blind."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        await blind.stop()

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, CoverOffMessage)
        assert sent_msg.channel == 1

    @pytest.mark.asyncio
    async def test_set_position(self, mock_module, mock_writer):
        """Test setting blind position."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        await blind.set_position(50)

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, CoverPosMessage)
        assert sent_msg.channel == 1
        assert sent_msg.position == 50

    @pytest.mark.asyncio
    async def test_set_position_fully_closed(self, mock_module, mock_writer):
        """Test setting blind position to fully closed uses close command."""
        blind = Blind(mock_module, 1, "Blind", False, True, 0x01)
        await blind.set_position(100)

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, CoverDownMessage)
        assert sent_msg.channel == 1
