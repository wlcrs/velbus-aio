"""Test cases for the Button channel class"""

from unittest.mock import Mock, patch

import pytest

from velbusaio.channels import Button, ButtonLedState
from velbusaio.messages.clear_led import ClearLedMessage
from velbusaio.messages.fast_blinking_led import FastBlinkingLedMessage
from velbusaio.messages.push_button_status import PushButtonStatusMessage
from velbusaio.messages.set_led import SetLedMessage
from velbusaio.messages.slow_blinking_led import SlowBlinkingLedMessage


class TestButton:
    """Test cases for the Button channel class."""

    def test_get_categories_enabled(self, mock_module, mock_writer):
        """Test button categories when enabled."""
        button = Button(mock_module, 1, "Button", False, True, 0x01)
        assert button.get_categories() == ["binary_sensor", "led", "button"]

    @pytest.mark.asyncio
    async def test_get_categories_disabled(self, mock_module, mock_writer):
        """Test button categories when disabled."""
        button = Button(mock_module, 1, "Button", False, True, 0x01)
        button.enabled = False
        await button.maybe_status_update()
        assert button.get_categories() == []

    @pytest.mark.asyncio
    async def test_is_closed(self, mock_module, mock_writer):
        """Test checking if button is closed (pressed)."""
        button = Button(mock_module, 1, "Button", False, True, 0x01)
        button.closed = True
        await button.maybe_status_update()
        assert button.is_closed()

        button.closed = False
        await button.maybe_status_update()
        assert not button.is_closed()

    @pytest.mark.asyncio
    async def test_is_long_pressed(self, mock_module, mock_writer):
        """Test checking if button is long pressed."""
        button = Button(mock_module, 1, "Button", False, True, 0x01)
        button.long = True
        await button.maybe_status_update()
        assert button.is_long_pressed()

        button.long = False
        await button.maybe_status_update()
        assert not button.is_long_pressed()

    @pytest.mark.asyncio
    async def test_is_on_led_on(self, mock_module, mock_writer):
        """Test checking if button LED is on."""
        button = Button(mock_module, 1, "Button", False, True, 0x01)
        button.led_state = ButtonLedState.ON
        await button.maybe_status_update()
        assert button.is_on()

    @pytest.mark.asyncio
    async def test_is_on_led_off(self, mock_module, mock_writer):
        """Test checking if button LED is off."""
        button = Button(mock_module, 1, "Button", False, True, 0x01)
        button.led_state = ButtonLedState.OFF
        await button.maybe_status_update()
        assert not button.is_on()

    @pytest.mark.asyncio
    async def test_set_led_state_on(self, mock_module, mock_writer):
        """Test setting button LED to on."""
        button = Button(mock_module, 1, "Button", False, True, 0x01)
        await button.set_led_state("on")

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, SetLedMessage)
        assert sent_msg.leds == [1]
        assert button.led_state == ButtonLedState.ON

    @pytest.mark.asyncio
    async def test_set_led_state_enum(self, mock_module, mock_writer):
        """Test setting button LED using ButtonLedState enum."""
        button = Button(mock_module, 1, "Button", False, True, 0x01)
        await button.set_led_state(ButtonLedState.FAST)

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, FastBlinkingLedMessage)
        assert sent_msg.leds == [1]
        assert button.led_state == ButtonLedState.FAST

    @pytest.mark.asyncio
    async def test_set_led_state_off(self, mock_module, mock_writer):
        """Test setting button LED to off."""
        button = Button(mock_module, 1, "Button", False, True, 0x01)
        await button.set_led_state("off")

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, ClearLedMessage)
        assert sent_msg.leds == [1]
        assert button.led_state == ButtonLedState.OFF

    @pytest.mark.asyncio
    async def test_set_led_state_slow(self, mock_module, mock_writer):
        """Test setting button LED to slow blink."""
        button = Button(mock_module, 1, "Button", False, True, 0x01)
        await button.set_led_state("slow")

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, SlowBlinkingLedMessage)
        assert sent_msg.leds == [1]
        assert button.led_state == ButtonLedState.SLOW

    @pytest.mark.asyncio
    async def test_set_led_state_fast(self, mock_module, mock_writer):
        """Test setting button LED to fast blink."""
        button = Button(mock_module, 1, "Button", False, True, 0x01)
        await button.set_led_state("fast")

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, FastBlinkingLedMessage)
        assert sent_msg.leds == [1]
        assert button.led_state == ButtonLedState.FAST

    @pytest.mark.asyncio
    async def test_press(self, mock_module, mock_writer):
        """Test pressing button."""
        button = Button(mock_module, 1, "Button", False, True, 0x01)
        await button.press()

        # Should be called twice: once for press, once for release
        assert mock_writer.call_count == 2
        press_msg = mock_writer.call_args_list[0][0][0]
        release_msg = mock_writer.call_args_list[1][0][0]
        assert isinstance(press_msg, PushButtonStatusMessage)
        assert isinstance(release_msg, PushButtonStatusMessage)
        assert press_msg.closed == [1]
        assert release_msg.opened == [1]
