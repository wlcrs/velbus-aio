"""Test cases for the Relay channel class"""

from unittest.mock import Mock, patch

import pytest

from velbusaio.channels import Relay
from velbusaio.messages.cancel_forced_off import CancelForcedOff
from velbusaio.messages.cancel_forced_on import CancelForcedOn
from velbusaio.messages.cancel_inhibit import CancelInhibit
from velbusaio.messages.forced_off import ForcedOff
from velbusaio.messages.forced_on import ForcedOn
from velbusaio.messages.inhibit import Inhibit
from velbusaio.messages.switch_relay_off import SwitchRelayOffMessage
from velbusaio.messages.switch_relay_on import SwitchRelayOnMessage


class TestRelay:
    """Test cases for the Relay channel class."""

    def test_get_categories_enabled(self, mock_module, mock_writer):
        """Test relay categories when enabled."""
        relay = Relay(mock_module, 1, "Relay", False, True, mock_writer, 0x01)
        assert relay.get_categories() == ["switch"]

    @pytest.mark.asyncio
    async def test_get_categories_disabled(self, mock_module, mock_writer):
        """Test relay categories when disabled."""
        relay = Relay(mock_module, 1, "Relay", False, True, mock_writer, 0x01)
        relay.enabled = False
        await relay.maybe_status_update()
        assert relay.get_categories() == []

    @pytest.mark.asyncio
    async def test_is_on(self, mock_module, mock_writer):
        """Test checking if relay is on."""
        relay = Relay(mock_module, 1, "Relay", False, True, mock_writer, 0x01)
        relay.on = True
        await relay.maybe_status_update()
        assert relay.is_on()

        relay.on = False
        await relay.maybe_status_update()
        assert not relay.is_on()

    @pytest.mark.asyncio
    async def test_is_inhibit(self, mock_module, mock_writer):
        """Test checking if relay is inhibited."""
        relay = Relay(mock_module, 1, "Relay", False, True, mock_writer, 0x01)
        relay.inhibit = True
        await relay.maybe_status_update()
        assert relay.is_inhibit()

    @pytest.mark.asyncio
    async def test_is_forced_on(self, mock_module, mock_writer):
        """Test checking if relay is forced on."""
        relay = Relay(mock_module, 1, "Relay", False, True, mock_writer, 0x01)
        relay.forced_on = True
        await relay.maybe_status_update()
        assert relay.is_forced_on()

    @pytest.mark.asyncio
    async def test_is_disabled(self, mock_module, mock_writer):
        """Test checking if relay is disabled."""
        relay = Relay(mock_module, 1, "Relay", False, True, mock_writer, 0x01)
        relay.disabled = True
        await relay.maybe_status_update()
        assert relay.is_disabled()

    @pytest.mark.asyncio
    async def test_turn_on(self, mock_module, mock_writer):
        """Test turning relay on."""
        relay = Relay(mock_module, 1, "Relay", False, True, mock_writer, 0x01)
        await relay.turn_on()

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, SwitchRelayOnMessage)
        assert 1 in sent_msg.relay_channels

    @pytest.mark.asyncio
    async def test_turn_off(self, mock_module, mock_writer):
        """Test turning relay off."""
        relay = Relay(mock_module, 1, "Relay", False, True, mock_writer, 0x01)
        await relay.turn_off()

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, SwitchRelayOffMessage)
        assert 1 in sent_msg.relay_channels

    @pytest.mark.asyncio
    async def test_set_forced_on(self, mock_module, mock_writer):
        """Test setting forced on."""
        relay = Relay(mock_module, 1, "Relay", False, True, mock_writer, 0x01)
        await relay.set_forced_on(True)
        assert isinstance(mock_writer.call_args[0][0], ForcedOn)

        mock_writer.reset_mock()
        await relay.set_forced_on(False)
        assert isinstance(mock_writer.call_args[0][0], CancelForcedOn)

    @pytest.mark.asyncio
    async def test_set_forced_off(self, mock_module, mock_writer):
        """Test setting forced off."""
        relay = Relay(mock_module, 1, "Relay", False, True, mock_writer, 0x01)
        await relay.set_forced_off(True)
        assert isinstance(mock_writer.call_args[0][0], ForcedOff)

        mock_writer.reset_mock()
        await relay.set_forced_off(False)
        assert isinstance(mock_writer.call_args[0][0], CancelForcedOff)

    @pytest.mark.asyncio
    async def test_set_inhibit(self, mock_module, mock_writer):
        """Test setting inhibit."""
        relay = Relay(mock_module, 1, "Relay", False, True, mock_writer, 0x01)
        await relay.set_inhibit(True)
        assert isinstance(mock_writer.call_args[0][0], Inhibit)

        mock_writer.reset_mock()
        await relay.set_inhibit(False)
        assert isinstance(mock_writer.call_args[0][0], CancelInhibit)

    def test_get_config_parameters_gated_by_commands(self, mock_module, mock_writer):
        """Test force/inhibit params are only advertised when supported."""
        relay = Relay(mock_module, 1, "Relay", False, True, mock_writer, 0x01)

        with patch.object(relay, "get_action_table", return_value=None):
            mock_module.has_command.side_effect = lambda code: (
                code in {0x12, 0x14, 0x16}
            )
            keys = {param.key for param in relay.get_config_parameters()}
            assert keys == {"name", "inhibit", "forced_on", "forced_off"}

        with patch.object(relay, "get_action_table", return_value=None):
            mock_module.has_command.side_effect = lambda code: code == 0x12
            keys = {param.key for param in relay.get_config_parameters()}
            assert keys == {"name", "forced_off"}

        with patch.object(relay, "get_action_table", return_value=None):
            mock_module.has_command.side_effect = None
            mock_module.has_command.return_value = False
            keys = {param.key for param in relay.get_config_parameters()}
            assert keys == {"name"}
