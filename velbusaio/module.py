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
        self.controller = controller
        self.address = module_address
        self.type = module_type
        self._log = logging.getLogger("velbus-module")

        self._name: str | None = None
        self._name_buffer: dict[
            int, str
        ] = {}  # temporary buffer while assembling name from memory blocks
        self.sub_addresses: dict[int, int] = {}
        self.serial = str(serial) if serial is not None else None
        self.memory_map_version = memorymap
        self.build_year = build_year
        self.build_week = build_week
        self.memory_map_outdated = False
        self._got_status = asyncio.Event()
        self._got_status.clear()
        self.channels: dict[int, Channel] = {}
        self.properties: dict[str, Property] = {}

        # load the strongly-typed spec via spec loader helper
        self.spec: ModuleSpec = load_module_spec(self.type, self._log)
        self._check_memory_map_build()
        commandRegistry.register_module_commands(
            self.type, self.spec.command_to_class
        )

        self._initialize_channels()
        self._initialize_properties()

        self.memory = MemoryBackend(self.address, self.send_message, self._log)
        if self.memory_map_outdated:
            self.memory.block_writes(
                f"module build {self.build} predates the memory map from "
                f"build {self.memory_map_build} that its spec describes"
            )
        self.action_tables = build_action_tables(
            self.memory,
            self.spec.memory.action_table,
            self._log,
            reserved=reserved_ranges(self.spec.memory),
        )

    @property
    def is_loaded(self) -> bool:
        """Return True if the module has finished its initial load."""
        return self._got_status.is_set()

    async def wait_for_status_messages(self) -> None:
        """Wait for status messages to be received."""
        try:
            await asyncio.wait_for(self._got_status.wait(), 2)
        except TimeoutError:
            self._log.warning(f"Timeout waiting for status messages for: {self}")

    @property
    def initial_timeout(self) -> int:
        """Get initial timeout for scanning module info."""
        return SCAN_MODULEINFO_TIMEOUT_INITIAL

    @property
    def build(self) -> str | None:
        """Return the firmware build as "YYWW", or None when unknown."""
        return format_build(self.build_year, self.build_week)

    @property
    def memory_map_build(self) -> str | None:
        """Return the build from which this spec's memory map applies."""
        return self.spec.memory_map_build

    def _check_memory_map_build(self) -> None:
        """Determine whether the module predates its spec's memory map."""
        self.memory_map_outdated = check_memory_map_outdated(
            self.address,
            self.type,
            self.build_year,
            self.build_week,
            self.spec,
            self._log,
        )

    def cleanup_sub_channels(self) -> None:
        """Cleanup subchannels that are not defined."""
        for sub in range(1, 4):
            if sub not in self.sub_addresses:
                for i in range(((sub * 8) + 1), (((sub + 1) * 8) + 1)):
                    if i in self.channels and not isinstance(
                        self.channels[i], channels_module.Temperature
                    ):
                        del self.channels[i]

    def __repr__(self) -> str:
        """Return string representation of the module."""
        return (
            f"<{self.name} "
            f"type:{self.type} "
            f"address:{self.address} "
            f"channels: {self.channels} "
            f"properties: {self.properties}>"
        )

    def __str__(self) -> str:
        """Return short string representation of the module."""
        return f"{self.address} ({self.type_name}: {self.name})"

    @property
    def addresses(self) -> list[int]:
        """Get all addresses for this module."""
        return [self.address, *self.sub_addresses.values()]

    def is_sub_address(self, channel_num: int) -> bool:
        """Check if channel is a subaddress channel."""
        sub_idx = (channel_num - 1) // 8
        return sub_idx in self.sub_addresses

    def set_sub_address(self, num: int, addr: int) -> None:
        """Set a subaddress for this module."""
        self.sub_addresses[num] = addr

    @property
    def type_name(self) -> str:
        """Get the module type name."""
        if self.spec.type_name:
            return self.spec.type_name
        return "UNKNOWN"

    @property
    def name(self) -> str:
        """Get the module name."""
        if self._name is not None and isinstance(self._name, str):
            return self._name
        return self.type_name

    @name.setter
    def name(self, value: str | None) -> None:
        self._name = value

    @property
    def sw_version(self) -> str:
        """Get the module software version."""
        return f"{self.build_year}.{self.build_week}"

    def has_command(self, code: int) -> bool:
        """Check if this module supports a given command code."""
        return commandRegistry.has_command(code, self.type)

    def create_message[M: Message](
        self,
        message_cls: type[M],
        address: int | None = None,
    ) -> M:
        """Create the correct module-specific Message variant."""
        target_addr = self.address if address is None else address
        code = getattr(message_cls, "_command_code", None)
        if code is not None:
            cls = commandRegistry.get_command(code, self.type)
            if cls is not None and issubclass(cls, message_cls):
                return cls(target_addr)
        return message_cls(target_addr)

    async def send_message(self, message: Message) -> None:
        """Send a message to the bus via the controller."""
        await self.controller.send(message)

    def calc_channel_offset(self, address: int) -> int:
        """Calculate channel offset based on address."""
        _channel_offset = 0
        if self.address != address:
            for _sub_addr_key, _sub_addr_val in self.sub_addresses.items():
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
            item = self.channels[channel]
            for key, val in updates.items():
                setattr(item, key, val)
            await item.maybe_status_update()
        except KeyError:
            self._log.error(
                f"channel {channel} does not exist for module @ address {self}"
            )

    async def _update_property(self, property_name: str, updates: dict) -> None:
        try:
            item = self.properties[property_name]
            for key, val in updates.items():
                setattr(item, key, val)
            await item.maybe_status_update()
        except KeyError:
            self._log.error(
                f"property {property_name} does not exist for module @ address {self}"
            )

    def get_action_table(self, channel: int) -> ActionTable | None:
        """Return the ActionTable for a channel, if defined in the module spec."""
        return self.action_tables.get(channel)

    def get_channel_enable_spec(self, channel: int) -> dict[str, int] | None:
        """Return EEPROM enable/disable metadata for a channel, if supported."""
        enable = self.spec.memory.channel_enable
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
        mrange = self.spec.memory.channels.get(channel)
        if mrange is None:
            return None
        return mrange.start, mrange.length

    def number_of_channels(self) -> int:
        """Retrieve the number of available channels in this module."""
        if not len(self.channels):
            return 0
        return max(self.channels.keys())

    async def _request_subaddresses(self) -> None:
        """Request module type / subaddresses."""
        await self.send_message(ModuleTypeRequestMessage(self.address))

    async def _process_memory_data_block_message(
        self, message: MemoryDataBlockMessage, channel_offset: int = 0
    ) -> None:
        if self.memory is not None:
            self.memory.feed_message(message)
        if not self.spec.memory.name_ranges or isinstance(self._name, str):
            return

        incoming_addr = join_address(message.high_address, message.low_address)
        range_byte_offset = 0
        total_bytes = sum(mr.length for mr in self.spec.memory.name_ranges)

        for mrange in self.spec.memory.name_ranges:
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
        if self.memory is not None:
            self.memory.feed_message(message)
        addr_int = join_address(message.high_address, message.low_address)
        if not self.spec.memory.address or addr_int not in self.spec.memory.address:
            return
        mdata = self.spec.memory.address[addr_int]
        if mdata.match is not None:
            for chan, chan_data in handle_match(mdata.match, message.data).items():
                data = chan_data.copy()
                if "PulsePerUnits" in data:
                    current_pulses = (
                        getattr(self.channels[chan], "pulses", None)
                        or getattr(self.channels[chan], "_pulses", 0)
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
        return self.channels.get(channel_id)

    def map_channel_number(self, channel: str | int) -> int:
        """Remap raw hardware packet channel byte to internal channel ID."""
        key = f"{int(channel):02X}"
        if key in self.spec.channel_number_map:
            return self.spec.channel_number_map[key]
        return int(channel)

    async def _request_module_status(self) -> None:
        """Request current state of channels."""
        if not self.spec.channels:
            return
        self._log.info(f"Request module status {self.address}")

        mod_stat_req_msg = ModuleStatusRequestMessage(self.address)
        counter_msg = None
        if self.spec.all_channel_status:
            mod_stat_req_msg.channels = self.spec.all_channel_status
        else:
            for chan_num, chan_spec in self.spec.channels.items():
                if chan_num < 9 and issubclass(
                    chan_spec.channel_class, (Blind, Dimmer, Relay)
                ):
                    mod_stat_req_msg.channels.append(chan_num)
                if issubclass(chan_spec.channel_class, ButtonCounter):
                    if counter_msg is None:
                        counter_msg = CounterStatusRequestMessage(self.address)
                    counter_msg.channels.append(chan_num)
        await self.send_message(mod_stat_req_msg)
        if counter_msg is not None:
            await self.send_message(counter_msg)

    async def _request_channel_name(self) -> None:
        msg_type = commandRegistry.get_command(
            CHANNEL_NAME_REQUEST_COMMAND_CODE, self.type
        )
        if msg_type is None:
            return
        msg = msg_type(self.address)
        msg.priority = PRIORITY_LOW
        if self.spec.all_channel_status:
            msg.channels = 0xFF
        else:
            msg.channels = list(range(1, (self.number_of_channels() + 1)))
        await self.send_message(msg)

    async def _request_memory(self) -> None:
        """Request all needed memory addresses."""
        if not self.spec.memory.name_ranges and not self.spec.memory.address:
            self.name = None
            return

        if self.type == 0x0C:
            self.name = None
            return

        for addr_int in self.spec.memory.address:
            msg = ReadDataFromMemoryMessage(self.address)
            msg.priority = PRIORITY_LOW
            msg.high_address = (addr_int >> 8) & 0xFF
            msg.low_address = addr_int & 0xFF
            await self.send_message(msg)

        for mrange in self.spec.memory.name_ranges:
            current_addr = mrange.start
            while current_addr <= mrange.end:
                block_msg = ReadDataBlockFromMemoryMessage(self.address)
                block_msg.priority = PRIORITY_LOW
                block_msg.high_address = (current_addr >> 8) & 0xFF
                block_msg.low_address = current_addr & 0xFF
                await self.send_message(block_msg)
                current_addr += 4

    def _initialize_properties(self) -> None:
        """Method for per module type initialization of properties."""
        for prop, prop_spec in self.spec.properties.items():
            self.properties[prop] = prop_spec.prop_class(
                module=self,
                name=prop_spec.name,
            )

    def _initialize_channels(self) -> None:
        """Initialize default module channels from spec."""
        for chan_num, chan_spec in self.spec.channels.items():
            cls = chan_spec.channel_class
            self.channels[chan_num] = cls(
                module=self,
                num=chan_num,
                name=chan_spec.name,
                nameEditable=chan_spec.editable,
                subDevice=chan_spec.subdevice,
                address=self.address,
            )
            if issubclass(cls, channels_module.Temperature) and (
                self.spec.thermostat
                or (self.spec.thermostat_addr is not None and self.spec.thermostat_addr != 0)
            ):
                self.channels[chan_num].thermostat = True
            if issubclass(cls, Dimmer) and self.spec.slider_scale:
                dimmer_channel = self.channels[chan_num]
                if isinstance(dimmer_channel, Dimmer):
                    dimmer_channel.slider_scale = self.spec.slider_scale


def __getattr__(name: str) -> Any:
    if name == "VmbDali":
        from velbusaio.vmbdali import VmbDali  # noqa: PLC0415

        return VmbDali
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
