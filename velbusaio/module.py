"""This represents a velbus module (hardware device)."""

# ruff: noqa: PLR0917

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import inspect
import logging
import struct
import types
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin, get_type_hints

if TYPE_CHECKING:
    from velbusaio.controller import Velbus as Controller

from velbusaio import channels as channels_module, properties as properties_module
from velbusaio.actions import (
    ActionSlot,
    ActionTable,
    build_action_tables,
    reserved_ranges,
)
from velbusaio.channels import ButtonCounter, Channel, Dimmer
from velbusaio.command_registry import commandRegistry
from velbusaio.config import decode_name, encode_name
from velbusaio.const import PRIORITY_LOW, SCAN_MODULEINFO_TIMEOUT_INITIAL
from velbusaio.helpers import handle_match, keys_exists
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
from velbusaio.module_cache import build_cache_dict, read_cache, save_cache
from velbusaio.module_spec_loader import (
    check_memory_map_outdated,
    format_build,
    load_module_spec,
)
from velbusaio.domains.climate.channel import Temperature, ThermostatChannel
from velbusaio.domains.cover.channel import Blind
from velbusaio.domains.input.channel import Button, ButtonCounter, Sensor
from velbusaio.domains.lighting.channel import Dimmer, Relay
from velbusaio.message_router import (
    dispatch_domain_handlers,
    extract_message_types,
    register_handler,
    route_module_message,
)
from velbusaio.properties import (
    BusErrorOff,
    BusErrorRx,
    BusErrorTx,
    LightValue,
    Property,
    PSUCurrent,
    PSULoad,
    PSUPower,
    PSUVoltage,
    SelectedProgram,
)


class Module:
    """Abstract class for Velbus hardware modules."""

    @classmethod
    def factory(
        cls,
        module_address: int,
        module_type: int,
        serial: int | str | None = None,
        memorymap: int | None = None,
        build_year: int | None = None,
        build_week: int | None = None,
        cache_dir: str | None = None,
        on_module_found: Callable[[Module], Awaitable[None]] | None = None,
    ) -> Module:
        """Module factory method."""
        if module_type in {0x45, 0x5A}:
            from velbusaio.vmbdali import VmbDali  # noqa: PLC0415

            return VmbDali(
                module_address,
                module_type,
                serial,
                memorymap,
                build_year,
                build_week,
                cache_dir,
                on_module_found,
            )

        return Module(
            module_address,
            module_type,
            serial,
            memorymap,
            build_year,
            build_week,
            cache_dir,
            on_module_found,
        )

    def __init__(
        self,
        module_address: int,
        module_type: int,
        serial: int | str | None = None,
        memorymap: int | None = None,
        build_year: int | None = None,
        build_week: int | None = None,
        cache_dir: str | None = None,
        on_module_found: Callable[[Module], Awaitable[None]] | None = None,
    ) -> None:
        """Initialize Module object."""
        self._address = module_address
        self._type = int(module_type)
        self._data: dict[str, Any] = {}

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
        self._cache_dir = cache_dir
        self._is_loading = False
        self._got_status = asyncio.Event()
        self._got_status.clear()
        self._channels: dict[int, Channel] = {}
        self._properties: dict[str, Property] = {}
        self._memory: MemoryBackend | None = None
        self._action_tables: dict[int, ActionTable] = {}
        self._message_handlers: dict[
            type[Message], list[Callable[[Any], Awaitable[None]]]
        ] = {}
        self.loaded = False
        self._use_cache = True
        self._loaded_cache: dict[str, Any] = {}
        self._cache_lock = asyncio.Lock()
        self._on_module_found: Callable[[Module], Awaitable[None]] | None = (
            on_module_found
        )
        self._controller: Controller | None = None
        self._log = logging.getLogger("velbus-module")
        self._writer: Callable[[Message], Awaitable[None]] | None = None

    async def wait_for_status_messages(self) -> None:
        """Wait for status messages to be received."""
        try:
            await asyncio.wait_for(self._got_status.wait(), 2)
        except TimeoutError:
            self._log.warning(f"Timeout waiting for status messages for: {self}")

    def get_initial_timeout(self) -> int:
        """Get initial timeout for scanning module info."""
        return SCAN_MODULEINFO_TIMEOUT_INITIAL

    async def initialize(
        self, writer: Callable[[Message], Awaitable[None]], controller: Controller
    ) -> None:
        """Initialize the module."""
        self._controller = controller
        self._log = logging.getLogger("velbus-module")

        # load the protocol data via spec loader helper
        self._data = await load_module_spec(self._type, self._log)

        self._check_memory_map_build()

        commandRegistry.register_module_commands(
            self._type, self._data.get("CommandToClass", {})
        )

        # set some params from the velbus controller
        self._writer = writer
        self._memory = MemoryBackend(self._address, writer, self._log)
        if self._memory_map_outdated:
            self._memory.block_writes(
                f"module build {self.get_build()} predates the memory map from "
                f"build {self.get_memory_map_build()} that its spec describes"
            )
        memory_spec = self._data.get("Memory", {})
        self._action_tables = build_action_tables(
            self._memory,
            memory_spec.get("ActionTable", {}),
            self._log,
            reserved=reserved_ranges(memory_spec),
        )
        for chan in self._channels.values():
            chan.set_writer(writer)

    def get_build(self) -> str | None:
        """Return the firmware build as "YYWW", or None when unknown."""
        return format_build(self.build_year, self.build_week)

    def get_memory_map_build(self) -> str | None:
        """Return the build from which this spec's memory map applies."""
        return self._data.get("MemoryMapBuild")

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
            self._data,
            self._log,
        )

    def cleanupSubChannels(self) -> None:
        """Cleanup subchannels that are not defined."""
        for sub in range(1, 4):
            if sub not in self._sub_address:
                for i in range(((sub * 8) + 1), (((sub + 1) * 8) + 1)):
                    if i in self._channels and not isinstance(
                        self._channels[i], channels_module.Temperature
                    ):
                        del self._channels[i]

    async def _cache(self) -> None:
        if not self._use_cache:
            return
        await save_cache(
            self._cache_dir,
            self._address,
            self.to_cache(),
            self._cache_lock,
            self._use_cache,
        )

    async def write_cache(self) -> None:
        """Persist this module's cache to disk."""
        await self._cache()

    def __getstate__(self) -> dict:
        """Get state for pickling."""
        d = self.__dict__
        return {
            k: d[k]
            for k in d
            if k not in {"_writer", "_log", "_controller", "_cache_lock"}
        }

    def __setstate__(self, state: dict) -> None:
        """Set state for unpickling."""
        self.__dict__ = state

    def __repr__(self) -> str:
        """Return string representation of the module."""
        return f"<{self._name} type:{self._type} address:{self._address} loaded:{self.loaded} loading:{self._is_loading} channels: {self._channels} properties: {self._properties}>"

    def __str__(self) -> str:
        """Return string representation of the module."""
        return self.__repr__()

    def to_cache(self) -> dict:
        """Build cache dict."""
        return build_cache_dict(self)

    def get_address(self) -> int:
        """Get the module address."""
        return self._address

    def get_addresses(self) -> list:
        """Get all addresses for this module."""
        res = [self._address]
        res.extend(self._sub_address.values())
        return res

    def get_sub_address_dict(self) -> dict[int, int]:
        """Return the sub addresses dict."""
        return self._sub_address

    def is_channel_active(self, channel_num: int) -> bool:
        """Check if a channel is active based on sub-address configuration."""
        if channel_num <= 8:
            return True
        sub_idx = (channel_num - 1) // 8
        return sub_idx in self._sub_address

    def add_subaddress(self, num: int, addr: int) -> None:
        """Add a subaddress to this module."""
        self._sub_address[num] = addr

    def get_type(self) -> int:
        """Get the module type."""
        return self._type

    def get_type_name(self) -> str:
        """Get the module type name."""
        if "Type" in self._data:
            return self._data["Type"]
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

    def get_serial(self) -> str | None:
        """Get the module serial number."""
        return self.serial

    def get_name(self) -> str:
        """Get the module name."""
        if isinstance(self._name, str):
            return self._name
        return ""

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

    def on_connect(self, meth: Callable[[], Awaitable[None]]) -> None:
        """Register a coroutine to be called on connect."""
        if self._controller:
            self._controller.add_connect_callback(meth)

    def remove_on_connect(self, meth: Callable[[], Awaitable[None]]) -> None:
        """Remove a previously registered on connect coroutine."""
        if self._controller:
            self._controller.remove_connect_callback(meth)

    def on_disconnect(self, meth: Callable[[], Awaitable[None]]) -> None:
        """Register a coroutine to be called on disconnect."""
        if self._controller:
            self._controller.add_disconnect_callback(meth)

    def remove_on_disconnect(self, meth: Callable[[], Awaitable[None]]) -> None:
        """Remove a previously registered on disconnect coroutine."""
        if self._controller:
            self._controller.remove_disconnect_callback(meth)

    async def _trigger_load_finished_callbacks(self) -> None:
        """Trigger all registered on load finished callbacks."""
        if self._on_module_found:
            try:
                await self._on_module_found(self)
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                self._log.error(f"Error in on_module_found callback: {e}")

    @property
    def is_connected(self) -> bool:
        """Return if the module is connected."""
        if self._controller:
            return self._controller.connected
        return False

    def register_message_handler(
        self,
        handler: Callable[[Any], Awaitable[None]],
        message_type: type[Message] | tuple[type[Message], ...] | None = None,
    ) -> None:
        """Register a message handler on this module."""
        if message_type is None:
            types_tuple = extract_message_types(handler)
        elif isinstance(message_type, tuple):
            types_tuple = message_type
        else:
            types_tuple = (message_type,)
        for msg_cls in types_tuple:
            self._message_handlers.setdefault(msg_cls, []).append(handler)

    async def dispatch_message(self, message: Message) -> bool:
        """Dispatch an incoming message to registered domain and module handlers."""
        handled_domain = await dispatch_domain_handlers(self, message)
        handlers = self._message_handlers.get(type(message), [])
        for handler in handlers:
            await handler(message)
        return handled_domain or bool(handlers)

    async def on_message(self, message: Message) -> None:
        """Process received message."""
        self._log.debug(f"RX: {message}")
        _channel_offset = self.calc_channel_offset(message.address)

        # Route message directly to channels and properties via message_router
        await route_module_message(self, message, _channel_offset, self._log)

        # Notify status
        self._got_status.set()

    async def _handle_bus_error_counter(
        self, message: Message, channel_offset: int = 0
    ) -> None:
        """Backward-compatible handler for bus error counter status."""
        await self.on_message(message)

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

    def get_channels(self) -> dict:
        """List all channels for this module."""
        return self._channels

    def get_properties(self) -> dict[str, Property]:
        """List all properties for this module."""
        return self._properties

    def get_memory(self) -> MemoryBackend | None:
        """Return the module memory backend, if initialized."""
        return self._memory

    def get_action_table(self, channel: int) -> ActionTable | None:
        """Return the action table for a channel, if this module has one."""
        return self._action_tables.get(channel)

    def get_action_tables(self) -> dict[int, ActionTable]:
        """Return all action tables for this module."""
        return dict(self._action_tables)

    def get_channel_enable_spec(self, channel: int) -> dict[str, int] | None:
        """Return EEPROM enable/disable metadata for a channel, if supported."""
        spec = self._data.get("Memory", {}).get("ChannelEnable")
        if not spec:
            return None
        address = spec.get("channels", {}).get(f"{channel:02d}")
        if address is None:
            return None
        return {
            "address": int(str(address), 16),
            "disabled_value": int(spec.get("disabled_value", 0xFF)),
            "enabled_value": int(spec.get("enabled_value", 0x01)),
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
        memory = self._data.get("Memory", {})
        channels = memory.get("Channels", {})
        key = f"{channel:02d}"
        if key not in channels:
            return None
        start_str, end_str = str(channels[key]).split("-")
        start = int(start_str, 16)
        end = int(end_str, 16)
        return start, end - start + 1

    async def set_channel_name_persistent(self, channel: int, name: str) -> None:
        """Write a channel name into module EEPROM and update the local name."""
        if self._memory is None:
            raise RuntimeError("Module memory backend is not initialized")
        name_range = self._channel_name_range(channel)
        if name_range is None:
            raise ValueError(f"Channel {channel} has no name memory range")
        start, length = name_range
        await self._memory.write_bytes(start, encode_name(name, length))
        if channel in self._channels:
            self._channels[channel].set_name(decode_name(encode_name(name, length)))
            await self._cache()

    async def load_from_vlp(self, vlp_data: Any) -> None:
        """Initialize the module from VLP data."""
        self._is_loading = True
        self._use_cache = False
        self._name = vlp_data.get_name()
        self._data["Channels"] = vlp_data.get_channels()
        await self._load_default_channels()
        await self._load_properties()
        for chan in self._channels.values():
            chan.set_loaded(True)
        self.loaded = True
        self._is_loading = False
        await self._request_module_status()
        await self._trigger_load_finished_callbacks()

    async def load(self, from_cache: bool = False) -> None:
        """Initialize the module."""
        self._is_loading = True
        cache = await self._get_cache()
        self._loaded_cache = cache
        await self._load_default_channels()
        await self._load_properties()

        if "name" in cache and isinstance(cache["name"], str) and cache["name"] != "":
            self._name = cache["name"]
        else:
            await self.__load_memory()

        if (self._use_cache or from_cache) and "sub_addresses" in cache:
            for num, addr in cache["sub_addresses"].items():
                self._sub_address[int(num)] = int(addr)
        elif self._writer:
            await self._writer(ModuleTypeRequestMessage(self._address))

        if "channels" in cache:
            for num, chan in cache["channels"].items():
                chan_num = int(num)
                if chan_num not in self._channels:
                    continue
                self._channels[chan_num].set_name(chan["name"])
                if "subdevice" in chan:
                    self._channels[chan_num].set_sub_device(chan["subdevice"])
                else:
                    self._channels[chan_num].set_sub_device(False)
                if "Unit" in chan:
                    unit_channel = self._channels[chan_num]
                    if isinstance(unit_channel, ButtonCounter):
                        unit_channel.set_unit(chan["Unit"])
                self._channels[chan_num].set_loaded(True)
        else:
            await self._request_channel_name()
        self._load()
        self._is_loading = False
        await self._request_module_status()
        await self._trigger_load_finished_callbacks()

    async def _get_cache(self) -> dict[str, Any]:
        """Read cache dictionary from disk."""
        return await read_cache(self._cache_dir, self._address, self._log)

    def _load(self) -> None:
        """Method for per module type loading."""

    def number_of_channels(self) -> int:
        """Retrieve the number of available channels in this module."""
        if not len(self._channels):
            return 0
        return max(self._channels.keys())

    async def set_memo_text(self, txt: str) -> None:
        """Set memo text property."""
        memo_prop = self._properties.get("memo_text")
        if not isinstance(memo_prop, properties_module.MemoText):
            return
        await memo_prop.set(txt)

    async def _process_memory_data_block_message(
        self, message: MemoryDataBlockMessage, channel_offset: int = 0
    ) -> None:
        if self._memory is not None:
            self._memory.feed_message(message)
        addr = f"{message.high_address:02X}{message.low_address:02X}"
        if "Memory" not in self._data:
            return
        if "ModuleName" not in self._data["Memory"]:
            return
        addr_data = self._data["Memory"]["ModuleName"]
        if isinstance(self._name, str):
            return
        ranges = []
        byte_offset = 0
        for block in addr_data.split(";"):
            start_str, end_str = block.split("-")
            start_addr = int("0x" + start_str, 0)
            end_addr = int("0x" + end_str, 0)
            ranges.append((start_addr, end_addr, byte_offset))
            byte_offset += end_addr - start_addr + 1
        incoming_addr = int("0x" + addr, 0)
        for start_addr, end_addr, range_byte_offset in ranges:
            if start_addr <= incoming_addr <= end_addr:
                position_in_range = incoming_addr - start_addr
                base_position = range_byte_offset + position_in_range
                for i, byte_val in enumerate(message.data):
                    char_position = base_position + i
                    self._name_buffer[char_position] = chr(byte_val)
                total_bytes = ranges[-1][2] + (ranges[-1][1] - ranges[-1][0] + 1)
                if len(self._name_buffer) >= total_bytes:
                    self._name = "".join(
                        str(x) for x in self._name_buffer.values() if x != chr(0xFF)
                    )
                    self._name_buffer = {}
                    await self._cache()
                break

    async def _process_memory_data_message(
        self, message: MemoryDataMessage, channel_offset: int = 0
    ) -> None:
        if self._memory is not None:
            self._memory.feed_message(message)
        addr_int = join_address(message.high_address, message.low_address)
        addr = f"{message.high_address:02X}{message.low_address:02X}"
        if "Memory" not in self._data:
            return
        if "Address" not in self._data["Memory"]:
            return
        if addr not in self._data["Memory"]["Address"]:
            return
        mdata = self._data["Memory"]["Address"][addr]
        if "Match" in mdata:
            for chan, chan_data in handle_match(mdata["Match"], message.data).items():
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
        if channel_obj.set_name_part(part, message.name) and self.loaded:
            await channel_obj.status_update()

    def get_channel(self, channel: str | int) -> Channel | None:
        """Return channel instance by packet channel number, applying hardware index remapping."""
        channel_id = self.map_channel_number(channel)
        return self._channels.get(channel_id)

    def map_channel_number(self, channel: str | int) -> int:
        """Remap raw hardware packet channel byte to internal channel ID."""
        if keys_exists(
            self._data,
            "ChannelNumbers",
            "Name",
            "Map",
            f"{int(channel):02X}",
        ):
            return int(
                self._data["ChannelNumbers"]["Name"]["Map"][f"{int(channel):02X}"]
            )
        return int(channel)

    def _translate_channel_name(self, channel: str | int) -> int:
        """Backward-compatible alias for map_channel_number."""
        return self.map_channel_number(channel)

    async def is_loaded(self) -> bool:
        """Check if all name messages have been received."""
        if self.loaded:
            return True
        if self._is_loading:
            return False
        if self._name_buffer:
            return False
        for chan in self._channels.values():
            if not chan.is_loaded():
                return False
        self.loaded = True
        await self._cache()
        return True

    async def _request_module_status(self) -> None:
        """Request current state of channels."""
        if "Channels" not in self._data:
            return
        self._log.info(f"Request module status {self._address}")

        mod_stat_req_msg = ModuleStatusRequestMessage(self._address)
        counter_msg = None
        if keys_exists(self._data, "AllChannelStatus"):
            mod_stat_req_msg.channels = self._data["AllChannelStatus"]
        else:
            for chan, chan_data in self._data["Channels"].items():
                if int(chan) < 9 and chan_data["Type"] in ("Blind", "Dimmer", "Relay"):
                    mod_stat_req_msg.channels.append(int(chan))
                if chan_data["Type"] == "ButtonCounter":
                    if counter_msg is None:
                        counter_msg = CounterStatusRequestMessage(self._address)
                    counter_msg.channels.append(int(chan))
        if self._writer:
            await self._writer(mod_stat_req_msg)
            if counter_msg is not None:
                await self._writer(counter_msg)

    async def _request_channel_name(self) -> None:
        msg_type = commandRegistry.get_command(
            CHANNEL_NAME_REQUEST_COMMAND_CODE, self.get_type()
        )
        if msg_type is None:
            return
        msg = msg_type(self._address)
        msg.priority = PRIORITY_LOW
        if keys_exists(self._data, "AllChannelStatus"):
            msg.channels = 0xFF
        else:
            msg.channels = list(range(1, (self.number_of_channels() + 1)))
        if self._writer:
            await self._writer(msg)

    async def __load_memory(self) -> None:
        """Request all needed memory addresses."""
        if "Memory" not in self._data:
            self._name = None
            return

        if self._type == 0x0C:
            self._name = None
            return

        if not self._writer:
            return

        for memory_key, memory_part in self._data["Memory"].items():
            if memory_key == "Address":
                for addr_int in memory_part:
                    addr = struct.unpack(
                        ">BB", struct.pack(">h", int("0x" + addr_int, 0))
                    )
                    msg = ReadDataFromMemoryMessage(self._address)
                    msg.priority = PRIORITY_LOW
                    msg.high_address = addr[0]
                    msg.low_address = addr[1]
                    await self._writer(msg)
            elif memory_key in {"ModuleName", "SensorName"}:
                for block in memory_part.split(";"):
                    addr_start_str, addr_end_str = block.split("-")
                    addr_start_int = int("0x" + addr_start_str, 0)
                    addr_end_int = int("0x" + addr_end_str, 0)
                    current_addr = addr_start_int
                    while current_addr <= addr_end_int:
                        block_end = min(current_addr + 3, addr_end_int)
                        addr_start = struct.unpack(
                            ">BB", struct.pack(">h", current_addr)
                        )
                        block_msg = ReadDataBlockFromMemoryMessage(self._address)
                        block_msg.priority = PRIORITY_LOW
                        block_msg.high_address = addr_start[0]
                        block_msg.low_address = addr_start[1]
                        await self._writer(block_msg)
                        current_addr = block_end + 1

    async def _load_properties(self) -> None:
        """Method for per module type loading of properties."""
        if "Properties" not in self._data:
            return

        for prop, prop_data in self._data["Properties"].items():
            if "Type" not in prop_data:
                continue
            prop_type = prop_data["Type"]
            try:
                cls = getattr(properties_module, prop_type)
            except AttributeError:
                self._log.error(
                    "Unknown property type '%s' for property '%s' on module address %s",
                    prop_type,
                    prop,
                    getattr(self, "_address", "unknown"),
                )
                continue
            self._properties[prop] = cls(
                module=self,
                name=prop_data.get("Name", prop),
                writer=self._writer,
            )

    async def _load_default_channels(self) -> None:
        if "Channels" not in self._data:
            return

        for chan, chan_data in self._data["Channels"].items():
            edit = True
            sub = True
            if "Editable" not in chan_data or chan_data["Editable"] != "yes":
                edit = False
            if "Subdevice" not in chan_data or chan_data["Subdevice"] != "yes":
                sub = False
            chan_type = chan_data["Type"]
            try:
                cls = getattr(channels_module, chan_type)
            except AttributeError:
                self._log.error(
                    "Unknown channel type '%s' for channel '%s' on module address %s",
                    chan_type,
                    chan,
                    getattr(self, "_address", "unknown"),
                )
                continue

            chan_num = int(chan)
            self._channels[chan_num] = cls(
                module=self,
                num=chan_num,
                name=chan_data["Name"],
                nameEditable=edit,
                subDevice=sub,
                writer=self._writer,
                address=self._address,
            )
            if chan_data["Type"] == "Temperature" and (
                "Thermostat" in self._data
                or (
                    "ThermostatAddr" in self._data and self._data["ThermostatAddr"] != 0
                )
            ):
                await self._update_channel(chan_num, {"thermostat": True})
            if chan_data["Type"] == "Dimmer" and "sliderScale" in self._data:
                dimmer_channel = self._channels[chan_num]
                if isinstance(dimmer_channel, Dimmer):
                    dimmer_channel.slider_scale = self._data["sliderScale"]




def __getattr__(name: str) -> Any:
    if name == "VmbDali":
        from velbusaio.vmbdali import VmbDali  # noqa: PLC0415

        return VmbDali
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
