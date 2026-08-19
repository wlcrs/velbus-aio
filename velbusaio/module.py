"""This represents a velbus module (hardware device)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from velbusaio.controller import Velbus as Controller

from velbusaio import channels as channels_module
from velbusaio.actions import (
    ActionSlot,
    ActionTable,
    build_action_tables,
    reserved_ranges,
)
from velbusaio.channels import ButtonCounter, Channel, Dimmer
from velbusaio.command_registry import commandRegistry
from velbusaio.const import PRIORITY_LOW, SCAN_MODULEINFO_TIMEOUT_INITIAL
from velbusaio.helpers import handle_match
from velbusaio.memory import MemoryBackend, join_address
from velbusaio.message import Message
from velbusaio.message_router import route_module_message
from velbusaio.messages.channel_name_part1 import ChannelNamePart1Message
from velbusaio.messages.channel_name_part2 import ChannelNamePart2Message
from velbusaio.messages.channel_name_part3 import ChannelNamePart3Message
from velbusaio.messages.channel_name_request import (
    COMMAND_CODE as CHANNEL_NAME_REQUEST_COMMAND_CODE,
)
from velbusaio.messages.counter_status_request import CounterStatusRequestMessage
from velbusaio.messages.memory_data import MemoryDataMessage
from velbusaio.messages.memory_data_block import MemoryDataBlockMessage
from velbusaio.messages.module_status_request import ModuleStatusRequestMessage
from velbusaio.messages.module_type_request import ModuleTypeRequestMessage
from velbusaio.messages.read_data_block_from_memory import (
    ReadDataBlockFromMemoryMessage,
)
from velbusaio.messages.read_data_from_memory import ReadDataFromMemoryMessage
from velbusaio.module_spec import ModuleSpec
from velbusaio.module_spec_loader import (
    check_memory_map_outdated,
    format_build,
    load_module_spec,
)
from velbusaio.properties import Property


class Module:
    """Abstract class for Velbus hardware modules."""

    @classmethod
    def factory(
        cls,
        module_address: int,
        module_type: int,
        *,
        controller: Controller,
        serial: int | str | None = None,
        memorymap: int | None = None,
        build_year: int | None = None,
        build_week: int | None = None,
    ) -> Module:
        """Module factory method."""
        if module_type in {0x45, 0x5A}:
            from velbusaio.vmbdali import VmbDali  # noqa: PLC0415

            return VmbDali(
                module_address,
                module_type,
                controller=controller,
                serial=serial,
                memorymap=memorymap,
                build_year=build_year,
                build_week=build_week,
            )

        return Module(
            module_address,
            module_type,
            controller=controller,
            serial=serial,
            memorymap=memorymap,
            build_year=build_year,
            build_week=build_week,
        )

    def __init__(
        self,
        module_address: int,
        module_type: int,
        *,
        controller: Controller,
        serial: int | str | None = None,
        memorymap: int | None = None,
        build_year: int | None = None,
        build_week: int | None = None,
    ) -> None:
        """Initialize Module object."""
        self._controller = controller
        self._address = module_address
        self._type = int(module_type)
        self._log = logging.getLogger("velbus-module")

        self._name: str | dict[Any, Any] | None = None
        self._name_buffer: dict[
            int, str
        ] = {}  # temporary buffer while assembling name from memory blocks
        self._sub_address: dict[int, int] = {}
        self.serial = str(serial) if serial is not None else None
        self.memory_map_version = memorymap
        self.build_year = build_year
        self.build_week = build_week
        self._memory_map_outdated = False
        self._got_status = asyncio.Event()
        self._got_status.clear()
        self._channels: dict[int, Channel] = {}
        self._properties: dict[str, Property] = {}

        # load the strongly-typed spec via spec loader helper
        self._spec: ModuleSpec = load_module_spec(self._type, self._log)
        self._check_memory_map_build()
        commandRegistry.register_module_commands(
            self._type, self._spec.command_to_class
        )

        self._initialize_channels()
        self._initialize_properties()

        self._memory = MemoryBackend(self._address, self.send_message, self._log)
        if self._memory_map_outdated:
            self._memory.block_writes(
                f"module build {self.get_build()} predates the memory map from "
                f"build {self.get_memory_map_build()} that its spec describes"
            )
        self._action_tables = build_action_tables(
            self._memory,
            self._spec.memory.action_table,
            self._log,
            reserved=reserved_ranges(self._spec.memory),
        )

    async def wait_for_status_messages(self) -> None:
        """Wait for status messages to be received."""
        try:
            await asyncio.wait_for(self._got_status.wait(), 2)
        except TimeoutError:
            self._log.warning(f"Timeout waiting for status messages for: {self}")

    def get_initial_timeout(self) -> int:
        """Get initial timeout for scanning module info."""
        return SCAN_MODULEINFO_TIMEOUT_INITIAL

    def get_build(self) -> str | None:
        """Return the firmware build as "YYWW", or None when unknown."""
        return format_build(self.build_year, self.build_week)

    def get_memory_map_build(self) -> str | None:
        """Return the build from which this spec's memory map applies."""
        return self._spec.memory_map_build

    def is_memory_map_outdated(self) -> bool:
        """Whether the module predates the memory map its spec describes."""
        return self._memory_map_outdated

    def _check_memory_map_build(self) -> None:
        """Determine whether the module predates its spec's memory map."""
        self._memory_map_outdated = check_memory_map_outdated(
            self._address,
            self._type,
            self.build_year,
            self.build_week,
            self._spec,
            self._log,
        )

    def cleanup_sub_channels(self) -> None:
        """Cleanup subchannels that are not defined."""
        for sub in range(1, 4):
            if sub not in self._sub_address:
                for i in range(((sub * 8) + 1), (((sub + 1) * 8) + 1)):
                    if i in self._channels and not isinstance(
                        self._channels[i], channels_module.Temperature
                    ):
                        del self._channels[i]

    def __repr__(self) -> str:
        """Return string representation of the module."""
        return (
            f"<{self.get_name()} "
            f"type:{self._type} "
            f"address:{self._address} "
            f"channels: {self._channels} "
            f"properties: {self._properties}>"
        )

    def __str__(self) -> str:
        """Return short string representation of the module."""
        return f"{self._address} ({self.get_type_name()}: {self.get_name()})"

    def get_address(self) -> int:
        """Get the module address."""
        return self._address

    def get_addresses(self) -> list[int]:
        """Get all addresses for this module."""
        return [self._address, *self._sub_address.values()]

    def get_sub_address_dict(self) -> dict[int, int]:
        """Return the sub addresses dict."""
        return self._sub_address

    def is_sub_address(self, channel_num: int) -> bool:
        """Check if channel is a subaddress channel."""
        sub_idx = (channel_num - 1) // 8
        return sub_idx in self._sub_address

    def set_sub_address(self, num: int, addr: int) -> None:
        """Set a subaddress for this module."""
        self._sub_address[num] = addr

    def get_type(self) -> int:
        """Get the module type."""
        return self._type

    def get_type_name(self) -> str:
        """Get the module type name."""
        if self._spec.type_name:
            return self._spec.type_name
        return "UNKNOWN"

    def has_command(self, code: int) -> bool:
        """Check if this module supports a given command code."""
        return commandRegistry.has_command(code, self.get_type())

    def create_message[M: Message](
        self,
        message_cls: type[M],
        address: int | None = None,
    ) -> M:
        """Create the correct module-specific Message variant."""
        target_addr = self._address if address is None else address
        code = getattr(message_cls, "_command_code", None)
        if code is not None:
            cls = commandRegistry.get_command(code, self.get_type())
            if cls is not None and issubclass(cls, message_cls):
                return cls(target_addr)
        return message_cls(target_addr)

    async def send_message(self, message: Message) -> None:
        """Send a message to the bus via the controller."""
        await self._controller.send(message)

    def get_serial(self) -> str | None:
        """Get the module serial number."""
        return self.serial

    def get_name(self) -> str | None:
        """Get the module name."""
        if self._name is not None and isinstance(self._name, str):
            return self._name
        return self.get_type_name()

    def get_sw_version(self) -> str:
        """Get the module software version."""
        return f"{self.build_year}.{self.build_week}"

    def calc_channel_offset(self, address: int) -> int:
        """Calculate channel offset based on address."""
        _channel_offset = 0
        if self._address != address:
            for _sub_addr_key, _sub_addr_val in self._sub_address.items():
                if _sub_addr_val == address:
                    _channel_offset = 8 * _sub_addr_key
                    break
        return _channel_offset

    async def on_message(self, message: Message) -> None:
        """Process received message."""
        self._log.debug(f"RX: {message}")
        _channel_offset = self.calc_channel_offset(message.address)

        # Route message directly to channels and properties via message_router
        await route_module_message(self, message, _channel_offset, self._log)

        # Notify status
        self._got_status.set()

    async def _update_channel(self, channel: int, updates: dict) -> None:
        try:
            item = self._channels[channel]
            for key, val in updates.items():
                setattr(item, key, val)
            await item.maybe_status_update()
        except KeyError:
            self._log.error(
                f"channel {channel} does not exist for module @ address {self}"
            )

    async def _update_property(self, property_name: str, updates: dict) -> None:
        try:
            item = self._properties[property_name]
            for key, val in updates.items():
                setattr(item, key, val)
            await item.maybe_status_update()
        except KeyError:
            self._log.error(
                f"property {property_name} does not exist for module @ address {self}"
            )

    def get_channels(self) -> dict[int, Channel]:
        """Get the module channels."""
        return self._channels

    def get_properties(self) -> dict[str, Property]:
        """Get the module properties."""
        return self._properties

    def get_memory(self) -> MemoryBackend | None:
        """Get module memory."""
        return self._memory

    def get_action_table(self, channel: int) -> ActionTable | None:
        """Return the ActionTable for a channel, if defined in the module spec."""
        return self._action_tables.get(channel)

    def get_action_tables(self) -> dict[int, ActionTable]:
        """Return all ActionTable instances for this module."""
        return self._action_tables

    def get_channel_enable_spec(self, channel: int) -> dict[str, int] | None:
        """Return EEPROM enable/disable metadata for a channel, if supported."""
        enable = self._spec.memory.channel_enable
        if not enable:
            return None
        address = enable.channels.get(channel)
        if address is None:
            return None
        return {
            "address": address,
            "disabled_value": enable.disabled_value,
            "enabled_value": enable.enabled_value,
        }

    async def load_action_table(
        self, channel: int, *, force: bool = False
    ) -> list[ActionSlot]:
        """Load (or reload) the action table for a channel."""
        table = self.get_action_table(channel)
        if table is None:
            return []
        return await table.load(force=force)

    def _channel_name_range(self, channel: int) -> tuple[int, int] | None:
        """Return (start, length) for a channel name memory range."""
        mrange = self._spec.memory.channels.get(channel)
        if mrange is None:
            return None
        return mrange.start, mrange.length

    def number_of_channels(self) -> int:
        """Retrieve the number of available channels in this module."""
        if not len(self._channels):
            return 0
        return max(self._channels.keys())

    async def _request_subaddresses(self) -> None:
        """Request module type / subaddresses."""
        await self.send_message(ModuleTypeRequestMessage(self._address))

    async def _process_memory_data_block_message(
        self, message: MemoryDataBlockMessage, channel_offset: int = 0
    ) -> None:
        if self._memory is not None:
            self._memory.feed_message(message)
        if not self._spec.memory.name_ranges or isinstance(self._name, str):
            return

        incoming_addr = join_address(message.high_address, message.low_address)
        range_byte_offset = 0
        total_bytes = sum(mr.length for mr in self._spec.memory.name_ranges)

        for mrange in self._spec.memory.name_ranges:
            if mrange.start <= incoming_addr <= mrange.end:
                position_in_range = incoming_addr - mrange.start
                base_position = range_byte_offset + position_in_range
                for i, byte_val in enumerate(message.data):
                    char_position = base_position + i
                    self._name_buffer[char_position] = chr(byte_val)
                if len(self._name_buffer) >= total_bytes:
                    self._name = "".join(
                        str(x) for x in self._name_buffer.values() if x != chr(0xFF)
                    )
                    self._name_buffer = {}
                break
            range_byte_offset += mrange.length

    async def _process_memory_data_message(
        self, message: MemoryDataMessage, channel_offset: int = 0
    ) -> None:
        if self._memory is not None:
            self._memory.feed_message(message)
        addr_int = join_address(message.high_address, message.low_address)
        if not self._spec.memory.address or addr_int not in self._spec.memory.address:
            return
        mdata = self._spec.memory.address[addr_int]
        if mdata.match is not None:
            for chan, chan_data in handle_match(mdata.match, message.data).items():
                data = chan_data.copy()
                if "PulsePerUnits" in data:
                    current_pulses = (
                        getattr(self._channels[chan], "pulses", None)
                        or getattr(self._channels[chan], "_pulses", 0)
                        or 0
                    )
                    if addr_int % 4 == 0:
                        new_pulses = (message.data << 8) + (current_pulses & 0xFF)
                    else:
                        new_pulses = (current_pulses & 0xFF00) + message.data
                    data["pulses"] = new_pulses
                await self._update_channel(chan, data)

    async def _process_channel_name_message(
        self,
        part: int,
        message: ChannelNamePart1Message
        | ChannelNamePart2Message
        | ChannelNamePart3Message,
    ) -> None:
        channel_obj = self.get_channel(message.channel)
        if channel_obj is None:
            return
        if channel_obj.set_name_part(part, message.name):
            await channel_obj.status_update()

    def get_channel(self, channel: str | int) -> Channel | None:
        """Return channel instance by packet channel number, applying hardware index remapping."""
        channel_id = self.map_channel_number(channel)
        return self._channels.get(channel_id)

    def map_channel_number(self, channel: str | int) -> int:
        """Remap raw hardware packet channel byte to internal channel ID."""
        key = f"{int(channel):02X}"
        if key in self._spec.channel_number_map:
            return self._spec.channel_number_map[key]
        return int(channel)

    async def _request_module_status(self) -> None:
        """Request current state of channels."""
        if not self._spec.channels:
            return
        self._log.info(f"Request module status {self._address}")

        mod_stat_req_msg = ModuleStatusRequestMessage(self._address)
        counter_msg = None
        if self._spec.all_channel_status:
            mod_stat_req_msg.channels = self._spec.all_channel_status
        else:
            for chan_num, chan_spec in self._spec.channels.items():
                if chan_num < 9 and issubclass(
                    chan_spec.channel_class, (Blind, Dimmer, Relay)
                ):
                    mod_stat_req_msg.channels.append(chan_num)
                if issubclass(chan_spec.channel_class, ButtonCounter):
                    if counter_msg is None:
                        counter_msg = CounterStatusRequestMessage(self._address)
                    counter_msg.channels.append(chan_num)
        await self.send_message(mod_stat_req_msg)
        if counter_msg is not None:
            await self.send_message(counter_msg)

    async def _request_channel_name(self) -> None:
        msg_type = commandRegistry.get_command(
            CHANNEL_NAME_REQUEST_COMMAND_CODE, self.get_type()
        )
        if msg_type is None:
            return
        msg = msg_type(self._address)
        msg.priority = PRIORITY_LOW
        if self._spec.all_channel_status:
            msg.channels = 0xFF
        else:
            msg.channels = list(range(1, (self.number_of_channels() + 1)))
        await self.send_message(msg)

    async def _request_memory(self) -> None:
        """Request all needed memory addresses."""
        if not self._spec.memory.name_ranges and not self._spec.memory.address:
            self._name = None
            return

        if self._type == 0x0C:
            self._name = None
            return

        for addr_int in self._spec.memory.address:
            msg = ReadDataFromMemoryMessage(self._address)
            msg.priority = PRIORITY_LOW
            msg.high_address = (addr_int >> 8) & 0xFF
            msg.low_address = addr_int & 0xFF
            await self.send_message(msg)

        for mrange in self._spec.memory.name_ranges:
            current_addr = mrange.start
            while current_addr <= mrange.end:
                block_msg = ReadDataBlockFromMemoryMessage(self._address)
                block_msg.priority = PRIORITY_LOW
                block_msg.high_address = (current_addr >> 8) & 0xFF
                block_msg.low_address = current_addr & 0xFF
                await self.send_message(block_msg)
                current_addr += 4

    def _initialize_properties(self) -> None:
        """Method for per module type initialization of properties."""
        for prop, prop_spec in self._spec.properties.items():
            self._properties[prop] = prop_spec.prop_class(
                module=self,
                name=prop_spec.name,
            )

    def _initialize_channels(self) -> None:
        """Initialize default module channels from spec."""
        for chan_num, chan_spec in self._spec.channels.items():
            cls = chan_spec.channel_class
            self._channels[chan_num] = cls(
                module=self,
                num=chan_num,
                name=chan_spec.name,
                nameEditable=chan_spec.editable,
                subDevice=chan_spec.subdevice,
                address=self._address,
            )
            if issubclass(cls, channels_module.Temperature) and (
                self._spec.thermostat
                or (self._spec.thermostat_addr is not None and self._spec.thermostat_addr != 0)
            ):
                self._channels[chan_num].thermostat = True
            if issubclass(cls, Dimmer) and self._spec.slider_scale:
                dimmer_channel = self._channels[chan_num]
                if isinstance(dimmer_channel, Dimmer):
                    dimmer_channel.slider_scale = self._spec.slider_scale


def __getattr__(name: str) -> Any:
    if name == "VmbDali":
        from velbusaio.vmbdali import VmbDali  # noqa: PLC0415

        return VmbDali
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
