"""Test cases for the Dimmer channel class"""

from unittest.mock import Mock, patch

import pytest

from velbusaio.channels import Dimmer
from velbusaio.messages.restore_dimmer import RestoreDimmerMessage
from velbusaio.messages.set_dimmer import SetDimmerMessage


class TestDimmer:
    """Test cases for the Dimmer channel class."""

    def test_init_default_scale(self, mock_module, mock_writer):
        """Test dimmer initialization with default scale."""
        dimmer = Dimmer(mock_module, 1, "Dimmer", False, True, 0x01)
        assert dimmer.slider_scale == 100

    def test_init_custom_scale(self, mock_module, mock_writer):
        """Test dimmer initialization with custom scale."""
        dimmer = Dimmer(
            mock_module, 1, "Dimmer", False, True, 0x01, slider_scale=254
        )
        assert dimmer.slider_scale == 254

    def test_get_categories(self, mock_module, mock_writer):
        """Test dimmer categories."""
        dimmer = Dimmer(mock_module, 1, "Dimmer", False, True, 0x01)
        assert dimmer.get_categories() == ["light"]

    @pytest.mark.asyncio
    async def test_is_on_when_on(self, mock_module, mock_writer):
        """Test checking if dimmer is on."""
        dimmer = Dimmer(mock_module, 1, "Dimmer", False, True, 0x01)
        dimmer.state = 50
        await dimmer.maybe_status_update()
        assert dimmer.is_on()

    @pytest.mark.asyncio
    async def test_is_on_when_off(self, mock_module, mock_writer):
        """Test checking if dimmer is off."""
        dimmer = Dimmer(mock_module, 1, "Dimmer", False, True, 0x01)
        dimmer.state = 0
        await dimmer.maybe_status_update()
        assert not dimmer.is_on()

    @pytest.mark.asyncio
    async def test_get_dimmer_state(self, mock_module, mock_writer):
        """Test getting dimmer state as percentage."""
        dimmer = Dimmer(mock_module, 1, "Dimmer", False, True, 0x01)
        dimmer.state = 50
        await dimmer.maybe_status_update()
        assert dimmer.get_dimmer_state() == 50

    @pytest.mark.asyncio
    async def test_get_dimmer_state_with_custom_scale(self, mock_module, mock_writer):
        """Test getting dimmer state with custom scale."""
        dimmer = Dimmer(
            mock_module, 1, "Dimmer", False, True, 0x01, slider_scale=254
        )
        dimmer.state = 127
        await dimmer.maybe_status_update()
        assert dimmer.get_dimmer_state() == 50

    @pytest.mark.asyncio
    async def test_set_dimmer_state(self, mock_module, mock_writer):
        """Test setting dimmer state."""
        dimmer = Dimmer(mock_module, 1, "Dimmer", False, True, 0x01)
        await dimmer.set_dimmer_state(75, transitiontime=5)

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, SetDimmerMessage)
        assert sent_msg.dimmer_state == 75
        assert sent_msg.dimmer_transitiontime == 5
        assert sent_msg.dimmer_channels == [1]

    @pytest.mark.asyncio
    async def test_restore_dimmer_state(self, mock_module, mock_writer):
        """Test restoring dimmer to last known state."""
        dimmer = Dimmer(mock_module, 1, "Dimmer", False, True, 0x01)
        await dimmer.restore_dimmer_state(transitiontime=3)

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, RestoreDimmerMessage)
        assert sent_msg.dimmer_transitiontime == 3
        assert sent_msg.dimmer_channels == [1]
