"""Velbus module scanner.

Handles bus scanning, module discovery, and cache loading.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import pathlib
import time
from typing import TYPE_CHECKING

import anyio

from velbusaio.const import SCAN_MODULETYPE_TIMEOUT
from velbusaio.message import Message
from velbusaio.messages.module_subtype import ModuleSubTypeMessage
from velbusaio.messages.module_type import ModuleTypeMessage
from velbusaio.module_cache import load_module_from_cache
from velbusaio.module_loader import load_module_from_bus

if TYPE_CHECKING:
    from velbusaio.controller import Velbus
    from velbusaio.module import Module


class VelbusScanner:
    """Disposable scanner for discovering Velbus modules on the bus."""

    def __init__(
        self,
        velbus: Velbus,
        one_address: int | None = None,
    ) -> None:
        """Initialize a VelbusScanner for a single scan session."""
        self._log = logging.getLogger("velbus-scanner")
        self._velbus = velbus
        self._one_address = one_address
        self._scan_lock = asyncio.Lock()
        self._full_scan_lock = asyncio.Lock()
        self.scan_complete = False
        self._scan_found_addresses: dict[int, ModuleTypeMessage | None] | None = None
        self._scan_sub_addresses: dict[int, dict[int, int]] = {}
        self.progress_callback: Callable[[str, str], None] | None = None

    def _report_progress(self, progress_type: str, value: str) -> None:
        """Report progress to the callback."""
        if self.progress_callback:
            self.progress_callback(progress_type, value)

    def empty_cache(self) -> bool:
        """Check if the cache is empty."""
        cache_dir = pathlib.Path(self._velbus.cache_dir)
        return len([name for name in cache_dir.iterdir() if name.is_file()]) == 0

    def on_message(self, rawmsg: Message) -> None:
        """Handle incoming messages during scanning."""
        if rawmsg.command == 0xFF or isinstance(rawmsg, ModuleTypeMessage):
            self._handle_module_type_response(rawmsg)
        elif rawmsg.command in (0xB0, 0xA7, 0xA6) or isinstance(
            rawmsg, ModuleSubTypeMessage
        ):
            self._handle_module_subtype_response(rawmsg)

    def _handle_module_type_response(self, rawmsg: Message) -> None:
        """Handle a received module type response packet."""
        address = rawmsg.address

        if self._scan_found_addresses is None:
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
        self._scan_found_addresses[address] = tmsg

    def _handle_module_subtype_response(self, rawmsg: Message) -> None:
        """Handle a received module subtype response packet."""
        if isinstance(rawmsg, ModuleSubTypeMessage):
            msg = rawmsg
        else:
            msg = ModuleSubTypeMessage.from_bytes(
                rawmsg.data_only or b"",
                address=rawmsg.address,
                priority=rawmsg.priority,
                rtr=rawmsg.rtr,
            )
            if rawmsg.command == 0xB0:
                msg.sub_address_offset = 0
            elif rawmsg.command == 0xA7:
                msg.sub_address_offset = 4
            elif rawmsg.command == 0xA6:
                msg.sub_address_offset = 8

        sub_list = {
            (msg.sub_address_offset + 1): msg.sub_address_1,
            (msg.sub_address_offset + 2): msg.sub_address_2,
            (msg.sub_address_offset + 3): msg.sub_address_3,
            (msg.sub_address_offset + 4): msg.sub_address_4,
        }

        # Track discovered subaddresses
        if msg.address not in self._scan_sub_addresses:
            self._scan_sub_addresses[msg.address] = {}
        for num, addr in sub_list.items():
            if addr != 0xFF:
                self._scan_sub_addresses[msg.address][num] = addr

        # If module already registered on controller, attach submodules immediately
        module = self._velbus.get_module(msg.address)
        if module is not None:
            self._velbus.add_submodules(module, sub_list)

    # Backwards-compatible aliases
    handle_module_type_response = _handle_module_type_response
    handle_module_type_response_async = _handle_module_type_response
    handle_module_subtype = _handle_module_subtype_response

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
        async with self._full_scan_lock:
            start_time = time.perf_counter()
            self._scan_complete = False

            self._log.debug("Waiting for Velbus bus to be ready to scan...")
            await (
                self._velbus.wait_on_all_messages_sent_async()
            )  # don't start a scan while messages are still in the queue
            self._log.debug("Velbus bus is ready to scan!")

            # Register message listener for type & subtype responses during scan
            self._velbus.add_message_listener(self.on_message)
            try:
                self._log.info("Sending scan type requests to all addresses...")
                start_scan_time = time.perf_counter()
                self._scan_found_addresses = {}
                self._scan_sub_addresses = {}
                for address in range(start_address, max_address):
                    cfile = pathlib.Path(
                        f"{self._velbus.cache_dir}/{address}.json"
                    )
                    if reload_cache and await anyio.Path(cfile).is_file():
                        self._log.info(
                            f"Reloading cache for address {address} ({address:#02x})"
                        )
                        await anyio.Path(cfile).unlink()

                    self._scan_found_addresses[address] = None
                    async with self._scan_lock:
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
                    for addr, msg in self._scan_found_addresses.items()
                    if msg is not None
                ]
                total_found = len(found_modules)
                current_loading = 0

                for address in range(start_address, max_address):
                    self._report_progress("scanning", str(address))
                    start_module_scan = time.perf_counter()
                    module_type_message: ModuleTypeMessage | None = (
                        self._scan_found_addresses[address]
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
                            self._velbus.cache_dir,
                            address,
                            controller=self._velbus,
                            module_type=module_type_message.module_type,
                            log=self._log,
                        )
                        if module is not None:
                            self._velbus.register_module(module)
                            if address in self._scan_sub_addresses:
                                self._velbus.add_submodules(
                                    module, self._scan_sub_addresses[address]
                                )
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
                            if address in self._scan_sub_addresses:
                                self._velbus.add_submodules(
                                    module, self._scan_sub_addresses[address]
                                )
                            await module.wait_for_status_messages()
                            module_scan_time = time.perf_counter() - start_module_scan
                            self._log.info(
                                f"Scan module {address} ({address:#02x}, {module.type_name}) completed in {module_scan_time:.2f}"
                            )
                            await self._velbus.save_module_cache(module)
                            await self._velbus._on_modules_loaded(module)
                    except TimeoutError:
                        self._log.error(
                            f"Module {address} ({address:#02x}) did not respond to info requests after successful type request"
                        )
            finally:
                self._velbus.remove_message_listener(self.on_message)
                self.scan_complete = True
                self._scan_found_addresses = None
                self._scan_sub_addresses = {}

            total_time = time.perf_counter() - start_time
            self._log.info(f"Module scan completed in {total_time:.2f} seconds")


Scanner = VelbusScanner
