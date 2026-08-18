"""Shared pytest fixtures for all test files"""

from unittest.mock import AsyncMock, Mock

import pytest


def pytest_configure(config):
    """Filter third-party deprecation warnings that are not actionable here."""
    config.addinivalue_line(
        "filterwarnings",
        "ignore:'asyncio.iscoroutinefunction' is deprecated:DeprecationWarning:backoff.*",
    )


@pytest.fixture
def mock_module():
    """Create a mock module for testing."""
    module = Mock()
    module.get_type.return_value = 0x01
    module.get_type_name.return_value = "TestModule"
    module.get_serial.return_value = "12345"
    module.get_addresses.return_value = [0x01, 0x02, 0x03, 0x04]
    module.get_sw_version.return_value = "1.0.0"
    module.get_name.return_value = "Test Module Name"
    module.calc_channel_offset.return_value = 0
    module.is_connected.return_value = True
    module.on_connect = Mock()
    module.remove_on_connect = Mock()
    module.on_disconnect = Mock()
    module.remove_on_disconnect = Mock()
    return module


@pytest.fixture
def mock_writer():
    """Create a mock writer for testing."""
    return AsyncMock()


def assert_roundtrip(
    msg: Any,
    expected_payload: bytes | bytearray,
    *,
    priority: Any = None,
    rtr: bool | None = None,
) -> None:
    """Assert that msg.data_to_binary() correctly encodes back to expected_payload bytes
    and verify message priority and rtr flags.

    Strips the command code header byte (byte 0) during payload comparison,
    and verifies that byte 0 matches msg._command_code.
    """
    if priority is not None:
        assert msg.priority == priority
    elif getattr(msg, "_priority", None) is not None:
        assert msg.priority == msg._priority

    if rtr is not None:
        assert msg.rtr == rtr
    elif getattr(msg, "_rtr", None) is not None:
        assert msg.rtr == msg._rtr

    binary = msg.data_to_binary()
    if getattr(msg, "rtr", False) or getattr(msg, "_rtr", False):
        assert binary == b""
    else:
        assert binary[0] == msg._command_code
        assert binary[1:] == bytes(expected_payload)
