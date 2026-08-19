"""Velbus packet handler.

:Author maikel punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from velbusaio.command_registry import commandRegistry
from velbusaio.message import Message
from velbusaio.module_spec_loader import broadcast_spec, ignore_spec

if TYPE_CHECKING:
    from velbusaio.controller import Velbus


class PacketHandler:
    """The PacketHandler class for processing and dispatching received bus packets."""

    def __init__(self, velbus: Velbus) -> None:
        """Initialize the PacketHandler class."""
        self._log = logging.getLogger("velbus-handler")
        self._velbus = velbus

    async def handle(self, rawmsg: Message) -> None:
        """Handle a received packet."""
        if rawmsg.address < 1 or rawmsg.address > 254:
            return
        if rawmsg.command is None:
            return

        priority = rawmsg.priority
        address = rawmsg.address
        rtr = rawmsg.rtr
        command_value = rawmsg.command
        data = rawmsg.data_only or b""
        hex_cmd = f"{command_value:02X}"

        # ignore broadcast
        if hex_cmd in broadcast_spec:
            self._log.debug(
                f"Received broadcast message {broadcast_spec[hex_cmd].name} from {address}, ignoring"
            )
            return

        # ignore messages
        if hex_cmd in ignore_spec:
            self._log.debug(
                f"Received ignored message {ignore_spec[hex_cmd].name} from {address}, ignoring"
            )
            return

        # handle messages for modules
        module = self._velbus.get_module(address)
        if module is not None:
            module_type = module.type
            if commandRegistry.has_command(int(command_value), module_type):
                command = commandRegistry.get_command(command_value, module_type)
                if not command:
                    return
                msg = command.from_bytes(
                    data, address=address, priority=priority, rtr=rtr
                )
                # send the message to the module
                await module.on_message(msg)
            else:
                self._log.warning(f"NOT FOUND IN command_registry: {rawmsg}")
