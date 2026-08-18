"""Test cases for VelbusProtocol data_received method (serial/streaming protocol)"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from velbusaio.const import MAXIMUM_MESSAGE_SIZE
from velbusaio.message import Message
from velbusaio.protocol import VelbusProtocol


class TestVelbusProtocolDataReceived:
    """Test cases for data_received method (serial/streaming protocol)."""

    @pytest.mark.asyncio
    async def test_data_received_valid_message(self):
        """Test receiving valid message data."""
        callback = AsyncMock()
        protocol = VelbusProtocol(callback)

        # Create a valid Velbus message
        valid_message = b"\x0f\xf8\x01\x00\x00\x00\x00\x00\x06\x04"

        with patch("velbusaio.message.Message.parse_frame") as mock_parse:
            mock_msg = Mock(spec=Message)
            mock_parse.return_value = (mock_msg, b"")

            protocol.data_received(valid_message)

            await asyncio.sleep(0.1)  # Allow async processing

            assert len(protocol._serial_buf) == 0
            mock_parse.assert_called_once()

    @pytest.mark.asyncio
    async def test_data_received_partial_message(self):
        """Test receiving partial message data."""
        callback = AsyncMock()
        protocol = VelbusProtocol(callback)

        # Partial message (incomplete)
        partial_message = b"\x0f\xf8\x01"

        protocol.data_received(partial_message)

        await asyncio.sleep(0.1)

        # Buffer should contain the partial data
        assert protocol._serial_buf == partial_message

    @pytest.mark.asyncio
    async def test_data_received_multiple_messages(self):
        """Test receiving multiple messages in one data chunk."""
        callback = AsyncMock()
        protocol = VelbusProtocol(callback)

        # Two valid messages back-to-back
        message1 = b"\x0f\xf8\x01\x00\x00\x00\x00\x00\x06\x04"
        message2 = b"\x0f\xf8\x02\x00\x00\x00\x00\x00\x05\x04"
        combined = message1 + message2

        with patch("velbusaio.message.Message.parse_frame") as mock_parse:
            mock_msg1 = Mock(spec=Message)
            mock_msg2 = Mock(spec=Message)

            mock_parse.side_effect = [
                (mock_msg1, message2),
                (mock_msg2, b""),
            ]

            protocol.data_received(combined)

            await asyncio.sleep(0.1)

            assert mock_parse.call_count >= 1

    @pytest.mark.asyncio
    async def test_data_received_invalid_message(self):
        """Test receiving invalid message data."""
        callback = AsyncMock()
        protocol = VelbusProtocol(callback)

        invalid_message = b"\xff\xff\xff\xff"

        with patch("velbusaio.message.Message.parse_frame") as mock_parse:
            mock_parse.return_value = (None, invalid_message)

            protocol.data_received(invalid_message)

            await asyncio.sleep(0.1)

            # Invalid data should remain in buffer
            assert len(protocol._serial_buf) > 0

    @pytest.mark.asyncio
    async def test_data_received_updates_activity_time(self):
        """Test that receiving data updates last activity time."""

        callback = AsyncMock()
        protocol = VelbusProtocol(callback)

        protocol._last_activity_time = 0

        protocol.data_received(b"\x0f\xf8")

        assert protocol._last_activity_time > 0

    @pytest.mark.asyncio
    async def test_data_received_buffer_overflow(self):
        """Test receiving data that exceeds maximum message size."""
        callback = AsyncMock()
        protocol = VelbusProtocol(callback)

        # Create data larger than MAXIMUM_MESSAGE_SIZE
        large_data = b"\x00" * (MAXIMUM_MESSAGE_SIZE + 100)

        with patch("velbusaio.message.Message.parse_frame") as mock_parse:
            mock_parse.return_value = (None, large_data[:MAXIMUM_MESSAGE_SIZE])

            protocol.data_received(large_data)

            await asyncio.sleep(0.1)

            # Should handle overflow gracefully
            assert len(protocol._serial_buf) <= len(large_data)

    @pytest.mark.asyncio
    async def test_data_received_message_callback(self):
        """Test that message callback is called when message is received."""
        callback = AsyncMock()
        protocol = VelbusProtocol(callback)

        valid_message = b"\x0f\xf8\x01\x00\x00\x00\x00\x00\x06\x04"

        with patch("velbusaio.message.Message.parse_frame") as mock_parse:
            mock_msg = Mock(spec=Message)
            mock_parse.return_value = (mock_msg, b"")

            protocol.data_received(valid_message)

            await asyncio.sleep(0.1)

            callback.assert_called_once_with(mock_msg)
