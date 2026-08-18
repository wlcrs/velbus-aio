"""Test utilities and assertion helpers."""

from __future__ import annotations

from typing import Any


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

