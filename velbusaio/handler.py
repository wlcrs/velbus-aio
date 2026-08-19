"""Velbus packet handler.

:Author maikel punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

import asyncio
import importlib.resources
import json
import logging
import pathlib
import time
from typing import TYPE_CHECKING

import anyio

from velbusaio.command_registry import commandRegistry
from velbusaio.const import SCAN_MODULEINFO_TIMEOUT_INTERVAL, SCAN_MODULETYPE_TIMEOUT
from velbusaio.message import Message
from velbusaio.messages.module_subtype import ModuleSubTypeMessage
from velbusaio.messages.module_type import ModuleTypeMessage
from velbusaio.module_cache import load_module_from_cache
from velbusaio.module_loader import load_module_from_bus

if TYPE_CHECKING:
    from velbusaio.controller import Velbus
    from velbusaio.module import Module


class PacketHandler:
    """The PacketHandler class."""

    def __init__(
        self,
        velbus: Velbus,
        one_address: int | None = None,
    ) -> None:
        """Initialize the PacketHandler class."""
        self._log = logging.getLogger("velbus-handler")
        self._velbus = velbus
        self._one_address = one_address
        self._typeResponseReceived = asyncio.Event()
        self._scanLock = asyncio.Lock()
        self._fullScanLock = asyncio.Lock()
        self._modulescan_address = 0
        self._scan_complete = False
        self._scan_delay_msec = 0
        self.__scan_found_addresses: dict[int, ModuleTypeMessage | None] | None = None
        self._progress_callback = None

    def set_progress_callback(self, callback):
        """Set a callback for scan progress updates."""
        self._progress_callback = callback

    def _report_progress(self, progress_type: str, value: str):
        """Report progress to the callback."""
        if self._progress_callback:
            self._progress_callback(progress_type, value)

    async def read_protocol_data(self):
        """Read the protocol data from the json files."""
        with importlib.resources.path(__name__, "module_spec/broadcast.json") as fspath:
            async with await anyio.open_file(fspath) as protocol_file:
                self.broadcast = json.loads(await protocol_file.read())
        with importlib.resources.path(__name__, "module_spec/ignore.json") as fspath:
            async with await anyio.open_file(fspath) as protocol_file:
                self.ignore = json.loads(await protocol_file.read())

    def empty_cache(self) -> bool:
        """Check if the cache is empty."""
        cache_dir = pathlib.Path(self._velbus.get_cache_dir())
        return len([name for name in cache_dir.iterdir() if name.is_file()]) == 0

    async def scan(self, reload_cache: bool = False) -> None:
        """Scan the Velbus bus for connected modules."""
        start_address = 1
        max_address = 254 + 1
        if self._one_address is not None:
            start_address = self._one_address
            max_address = self._one_address + 1
            self._log.info(
                f"Scanning only one address {self._one_address} ({self._one_address:#02x})"
            )

        self._log.info("Start module scan")
        async with self._fullScanLock:
            start_time = time.perf_counter()
            self._scan_complete = False

            self._log.debug("Waiting for Velbus bus to be ready to scan...")
            await (
                self._velbus.wait_on_all_messages_sent_async()
            )  # don't start a scan while messages are still in the queue
            self._log.debug("Velbus bus is ready to scan!")

            self._log.info("Sending scan type requests to all addresses...")
            start_scan_time = time.perf_counter()
            self.__scan_found_addresses = {}
            for address in range(start_address, max_address):
                cfile = pathlib.Path(f"{self._velbus.get_cache_dir()}/{address}.json")
                if reload_cache and await anyio.Path(cfile).is_file():
                    self._log.info(
                        f"Reloading cache for address {address} ({address:#02x})"
                    )
                    await anyio.Path(cfile).unlink()

                self.__scan_found_addresses[address] = None
                async with self._scanLock:
                    await self._velbus.sendTypeRequestMessage(address)

            await self._velbus.wait_on_all_messages_sent_async()
            scan_time = time.perf_counter() - start_scan_time
            self._log.info(
                f"Sent scan type requests to all addresses in {scan_time:.2f}. Going to wait for responses..."
            )

            await asyncio.sleep(SCAN_MODULETYPE_TIMEOUT / 1000)  # wait for responses

            self._log.info(
                "Waiting for responses done. Going to check for responses..."
            )
            found_modules = [
                addr
                for addr, msg in self.__scan_found_addresses.items()
                if msg is not None
            ]
            total_found = len(found_modules)
            current_loading = 0

            for address in range(start_address, max_address):
                self._report_progress("scanning", str(address))
                start_module_scan = time.perf_counter()
                module_type_message: ModuleTypeMessage | None = (
                    self.__scan_found_addresses[address]
                )
                if module_type_message is not None:
                    current_loading += 1
                    m_name = module_type_message.module_type_name()
                    self._report_progress(
                        "loading", f"{current_loading}/{total_found} ({m_name})"
                    )

                module: Module | None = None
                if module_type_message is None:
                    self._log.debug(
                        f"No module found at address {address} ({address:#02x}). Skipping it."
                    )
                    continue

                self._log.info(
                    f"Found module at address {address} ({address:#02x}): {module_type_message.module_type_name()}"
                )

                try:
                    module = await load_module_from_cache(
                        self._velbus.get_cache_dir(),
                        address,
                        controller=self._velbus,
                        module_type=module_type_message.module_type,
                        log=self._log,
                    )
                    if module is not None:
                        self._velbus.register_module(module)
                        await module._request_module_status()
                        await self._velbus._on_modules_loaded(module)
                    else:
                        module = await load_module_from_bus(
                            address,
                            module_type_message.module_type,
                            controller=self._velbus,
                            serial=module_type_message.serial,
                            memorymap=module_type_message.memory_map_version,
                            build_year=module_type_message.build_year,
                            build_week=module_type_message.build_week,
                            log=self._log,
                        )
                        self._velbus.register_module(module)
                        await module.wait_for_status_messages()
                        module_scan_time = time.perf_counter() - start_module_scan
                        self._log.info(
                            f"Scan module {address} ({address:#02x}, {module.get_type_name()}) completed in {module_scan_time:.2f}"
                        )
                        await self._velbus.save_module_cache(module)
                        await self._velbus._on_modules_loaded(module)
                except TimeoutError:
                    self._log.error(
                        f"Module {address} ({address:#02x}) did not respond to info requests after successful type request"
                    )

            self._scan_complete = True
            total_time = time.perf_counter() - start_time
            self._log.info(f"Module scan completed in {total_time:.2f} seconds")

    async def __handle_module_type_response_async(self, rawmsg: Message) -> None:
        """Handle a received module type response packet."""
        address = rawmsg.address

        if self.__scan_found_addresses is None:
            self._log.warning(
                f"Received module type response for address {address} ({address:#02x}) but no scan in progress"
            )
            return

        if isinstance(rawmsg, ModuleTypeMessage):
            tmsg = rawmsg
        else:
            tmsg = ModuleTypeMessage.from_bytes(
                rawmsg.data_only or b"",
                address=address,
                priority=rawmsg.priority,
                rtr=rawmsg.rtr,
            )
        self._log.debug(
            f"A '{tmsg.module_type_name()}' ({tmsg.module_type:#02x}) lives on address {address} ({address:#02x})"
        )
        self.__scan_found_addresses[address] = tmsg

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

        # handle module type response message
        if command_value == 0xFF:
            await self.__handle_module_type_response_async(rawmsg)

        # handle module subtype response message
        elif command_value in (0xB0, 0xA7, 0xA6) and not self._scan_complete:
            msg: ModuleSubTypeMessage = ModuleSubTypeMessage.from_bytes(
                data, address=address, priority=priority, rtr=rtr
            )
            if command_value == 0xB0:
                msg.sub_address_offset = 0
            elif command_value == 0xA7:
                msg.sub_address_offset = 4
            elif command_value == 0xA6:
                msg.sub_address_offset = 8
            async with self._scanLock:
                self._scan_delay_msec += SCAN_MODULEINFO_TIMEOUT_INTERVAL
                self._handle_module_subtype(msg)

        # ignore broadcast
        elif hex_cmd in self.broadcast:
            self._log.debug(
                f"Received broadcast message {self.broadcast[hex_cmd]['Name']} from {address}, ignoring"
            )

        # ignore messages
        elif hex_cmd in self.ignore:
            self._log.debug(
                f"Received ignored message {self.ignore[hex_cmd]['Name']} from {address}, ignoring"
            )

        # handle other messages for modules that are already scanned
        else:
            module = None
            async with self._scanLock:
                module = self._velbus.get_module(address)
            if module is not None:
                module_type = module.get_type()
                if commandRegistry.has_command(int(command_value), module_type):
                    command = commandRegistry.get_command(command_value, module_type)
                    if not command:
                        return
                    msg = command.from_bytes(
                        data, address=address, priority=priority, rtr=rtr
                    )

                    # restart the info completion time when info message received
                    if command_value in (
                        0xF0,
                        0xF1,
                        0xF2,
                        0xFB,
                        0xFE,
                        0xCC,
                    ):  # names, memory data, memory block
                        self._scan_delay_msec += SCAN_MODULEINFO_TIMEOUT_INTERVAL
                        # self._log.debug(f"Restart timeout {msg}")
                    # send the message to the modules
                    await module.on_message(msg)
                else:
                    self._log.warning(f"NOT FOUND IN command_registry: {rawmsg}")

    def _handle_module_subtype(self, msg: ModuleSubTypeMessage) -> None:
        """Handle a received module subtype packet."""
        module = self._velbus.get_module(msg.address)
        if module is not None:
            addrList = {
                (msg.sub_address_offset + 1): msg.sub_address_1,
                (msg.sub_address_offset + 2): msg.sub_address_2,
                (msg.sub_address_offset + 3): msg.sub_address_3,
                (msg.sub_address_offset + 4): msg.sub_address_4,
            }
            self._velbus.add_submodules(module, addrList)


#    def _channel_convert(self, module: str, channel: str, ctype: str) -> None | int:
#        data = keys_exists(
#            self.pdata, "ModuleTypes", h2(module), "ChannelNumbers", ctype
#        )
#        if data and "Map" in data and h2(channel) in data["Map"]:
#            return data["Map"][h2(channel)]
#        if data and "Convert" in data:
#            return int(channel)
#        for offset in range(0, 8):
#            if channel & (1 << offset):
#                return offset + 1
#        return None
