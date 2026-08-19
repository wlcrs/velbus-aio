"""Test cases for the Memo channel class"""

from unittest.mock import Mock, patch

import pytest

from velbusaio.messages.memo_text import MemoTextMessage
from velbusaio.properties import MemoText


class TestMemo:
    """Test cases for the Memo channel class."""

    @pytest.mark.asyncio
    async def test_set_short_text(self, mock_module, mock_writer):
        """Test setting short memo text."""
        memo = MemoText(mock_module, "Memo")
        await memo.set("Test")

        # Should be called once for short text
        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, MemoTextMessage)
        assert sent_msg.name == "Test"
        assert memo.value == "Test"

    @pytest.mark.asyncio
    async def test_set_long_text(self, mock_module, mock_writer):
        """Test setting long memo text."""
        memo = MemoText(mock_module, "Memo")
        await memo.set("This is a long text message")

        # Should be called multiple times for long text (chunks of 5)
        assert mock_writer.call_count > 1
        for call in mock_writer.call_args_list:
            assert isinstance(call[0][0], MemoTextMessage)
        assert memo.value == "This is a long text message"
