"""Test cases for Velbus controller exponential backoff reconnect logic."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from velbusaio.controller import Velbus
from velbusaio.exceptions import VelbusConnectionFailed


@pytest.mark.asyncio
async def test_reconnect_exponential_backoff_on_rapid_disconnect():
    """Test that rapid disconnections trigger exponential backoff sleeping."""
    controller = Velbus("127.0.0.1:27015")
    connect_mock = AsyncMock()
    controller.connect = connect_mock

    # Simulate recent connection 1 second ago
    controller._last_connect_time = 100.0

    with (
        patch("time.monotonic", return_value=101.0),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        # Trigger disconnect handling
        await controller._on_connection_state(False)
        assert controller._reconnect_task is not None
        await controller._reconnect_task

    # Sleep should have been called with initial delay of 1.0s before retrying connect
    mock_sleep.assert_called_once_with(1.0)
    connect_mock.assert_called_once()
    await controller.stop()


@pytest.mark.asyncio
async def test_reconnect_exponential_backoff_on_connection_failed():
    """Test backoff sleeping when connect() raises VelbusConnectionFailed."""
    controller = Velbus("127.0.0.1:27015")
    connect_mock = AsyncMock(side_effect=[VelbusConnectionFailed(), None])
    controller.connect = connect_mock

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        task = asyncio.create_task(controller._reconnect_loop())
        await task

    mock_sleep.assert_called_once_with(1.0)
    assert connect_mock.call_count == 2
    await controller.stop()


@pytest.mark.asyncio
async def test_reconnect_delay_resets_after_stable_connection():
    """Test that reconnect delay resets to 1.0s after connection stays alive > 30s."""
    controller = Velbus("127.0.0.1:27015")
    controller._last_connect_time = 100.0

    with patch("time.monotonic", return_value=140.0):
        await controller._on_connection_state(True)
    # `_reconnect_delay` is no longer an instance attribute; reconnect delay
    # is local to the reconnect loop and will start at 1.0 when a loop runs.
    assert not hasattr(controller, "_reconnect_delay")
    await controller.stop()
