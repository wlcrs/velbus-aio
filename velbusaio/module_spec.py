"""Strongly-typed dataclasses for Velbus module specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, NewType

import velbusaio.channels as channels_module
from velbusaio.command_registry import MESSAGE_CATALOG
import velbusaio.messages  # noqa: F401 - ensures all message subclasses are registered
import velbusaio.properties as properties_module

if TYPE_CHECKING:
    from velbusaio.channels import Channel
    from velbusaio.message import Message
    from velbusaio.properties import Property


@dataclass(frozen=True, slots=True)
class ChannelSpec:
    """Specification for a module channel."""

    name: str
    channel_class: type[Channel]
    editable: bool = False
    subdevice: bool = False

    @property
    def channel_type(self) -> str:
        """String name of the channel type."""
        return self.channel_class.__name__

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChannelSpec:
        """Create a ChannelSpec from dictionary data."""
        type_val = data.get("Type", "")
        if isinstance(type_val, type):
            chan_cls = type_val
        elif isinstance(type_val, str) and type_val:
            chan_cls = getattr(channels_module, type_val, None)
            if chan_cls is None or not isinstance(chan_cls, type):
                raise KeyError(f"Unknown channel type '{type_val}' in channel spec")
        else:
            raise ValueError(f"Missing or invalid channel Type in channel spec: {data!r}")

        return cls(
            name=data.get("Name", ""),
            channel_class=chan_cls,
            editable=data.get("Editable") == "yes",
            subdevice=data.get("Subdevice") == "yes",
        )


@dataclass(frozen=True, slots=True)
class PropertySpec:
    """Specification for a module property."""

    name: str
    prop_class: type[Property]

    @property
    def prop_type(self) -> str:
        """String name of the property type."""
        return self.prop_class.__name__

    @classmethod
    def from_dict(cls, key: str, data: dict[str, Any]) -> PropertySpec:
        """Create a PropertySpec from dictionary data."""
        type_val = data.get("Type", "")
        if isinstance(type_val, type):
            prop_cls = type_val
        elif isinstance(type_val, str) and type_val:
            prop_cls = getattr(properties_module, type_val, None)
            if prop_cls is None or not isinstance(prop_cls, type):
                raise KeyError(
                    f"Unknown property type '{type_val}' for property '{key}' in spec"
                )
        else:
            raise ValueError(f"Missing or invalid property Type for property '{key}': {data!r}")

        return cls(
            name=data.get("Name", key),
            prop_class=prop_cls,
        )


@dataclass(frozen=True, slots=True)
class ActionTableChannelSpec:
    """Specification for one channel's action table EEPROM mapping."""

    bank: int | None = None
    noc_address: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionTableChannelSpec:
        """Create an ActionTableChannelSpec from dictionary data."""
        bank_val = data.get("bank")
        noc_val = data.get("noc_address")
        return cls(
            bank=int(str(bank_val), 16) if bank_val is not None else None,
            noc_address=int(str(noc_val), 16) if noc_val is not None else None,
        )


@dataclass(frozen=True, slots=True)
class ActionTableSpec:
    """Specification for an action table in module EEPROM."""

    actions: str = ""
    slot_count: int = 0
    slot_size: int = 0
    bank: int | None = None
    layout: str | None = None
    release_bit: bool | None = None
    subject_encoding: str | None = None
    kind: str | None = None
    channels: dict[int, ActionTableChannelSpec] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ActionTableSpec:
        """Create an ActionTableSpec from dictionary data."""
        bank_val = data.get("bank")
        channels_raw = data.get("channels", {})
        channels = {
            int(k): (
                v
                if isinstance(v, ActionTableChannelSpec)
                else ActionTableChannelSpec.from_dict(v)
            )
            for k, v in channels_raw.items()
        }
        return cls(
            actions=data.get("actions", ""),
            slot_count=int(data.get("slot_count", 0)),
            slot_size=int(data.get("slot_size", 0)),
            bank=int(str(bank_val), 16) if bank_val is not None else None,
            layout=data.get("layout"),
            release_bit=data.get("release_bit"),
            subject_encoding=data.get("subject_encoding"),
            kind=data.get("kind"),
            channels=channels,
        )


@dataclass(frozen=True, slots=True)
class ChannelEnableSpec:
    """Specification for channel enable EEPROM layout."""

    channels: dict[int, int] = field(default_factory=dict)
    disabled_value: int = 0xFF
    enabled_value: int = 0x01

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChannelEnableSpec:
        """Create a ChannelEnableSpec from dictionary data."""
        channels_raw = data.get("channels", {})
        channels = {
            int(k): int(str(v), 16)
            for k, v in channels_raw.items()
        }
        return cls(
            channels=channels,
            disabled_value=int(data.get("disabled_value", 0xFF)),
            enabled_value=int(data.get("enabled_value", 0x01)),
        )


BitPattern = NewType("BitPattern", str)
RuleId = NewType("RuleId", str)
MatchActionKey = Literal["Value", "Channel", "SubName", "Data", "PulsePerUnits"]
MatchRuleMap = dict[RuleId, dict[BitPattern, dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class MemoryAddressSpec:
    """Specification for decoding values from a specific EEPROM memory address."""

    match: MatchRuleMap | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryAddressSpec:
        """Create a MemoryAddressSpec from dictionary data."""
        match_raw = data.get("Match")
        if match_raw is not None and isinstance(match_raw, dict):
            match: MatchRuleMap = {
                RuleId(str(rule_id)): {
                    BitPattern(str(pat)): dict(action)
                    for pat, action in bit_patterns.items()
                    if isinstance(action, dict)
                }
                for rule_id, bit_patterns in match_raw.items()
                if isinstance(bit_patterns, dict)
            }
        else:
            match = None
        return cls(match=match)


@dataclass(frozen=True, slots=True)
class MemoryRange:
    """A range of memory addresses (start and end inclusive)."""

    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    @classmethod
    def from_str(cls, s: str) -> MemoryRange:
        """Parse a hex range string formatted as '00F0-00FF'."""
        start_str, end_str = s.strip().split("-")
        return cls(
            start=int(start_str, 16),
            end=int(end_str, 16),
        )


@dataclass(frozen=True, slots=True)
class MemorySpec:
    """Specification for module EEPROM memory layout."""

    module_name: str | None = None
    sensor_name: str | None = None
    name_ranges: tuple[MemoryRange, ...] = ()
    channels: dict[int, MemoryRange] = field(default_factory=dict)
    address: dict[int, MemoryAddressSpec] = field(default_factory=dict)
    channel_enable: ChannelEnableSpec | None = None
    action_table: ActionTableSpec | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemorySpec:
        """Create a MemorySpec from dictionary data."""
        action_table_data = data.get("ActionTable")
        action_table = (
            ActionTableSpec.from_dict(action_table_data)
            if isinstance(action_table_data, dict)
            else None
        )

        enable_data = data.get("ChannelEnable")
        channel_enable = (
            ChannelEnableSpec.from_dict(enable_data)
            if isinstance(enable_data, dict)
            else None
        )

        # Pre-parse name ranges from ModuleName and SensorName
        name_ranges: list[MemoryRange] = []
        module_name = data.get("ModuleName")
        sensor_name = data.get("SensorName")
        for name_field in (module_name, sensor_name):
            if not name_field or not isinstance(name_field, str):
                continue
            for part in name_field.split(";"):
                part = part.strip()
                if "-" in part:
                    name_ranges.append(MemoryRange.from_str(part))

        # Pre-parse channel memory ranges
        channels: dict[int, MemoryRange] = {}
        for chan_k, chan_v in data.get("Channels", {}).items():
            if not isinstance(chan_v, str) or "-" not in chan_v:
                continue
            chan_num = (
                int(chan_k, 16)
                if isinstance(chan_k, str) and not chan_k.isdigit()
                else int(chan_k)
            )
            channels[chan_num] = MemoryRange.from_str(chan_v)

        # Pre-parse address keys and specs
        address: dict[int, MemoryAddressSpec] = {}
        for addr_str, addr_data in data.get("Address", {}).items():
            addr_int = (
                int(addr_str, 16) if isinstance(addr_str, str) else int(addr_str)
            )
            address[addr_int] = (
                addr_data
                if isinstance(addr_data, MemoryAddressSpec)
                else MemoryAddressSpec.from_dict(addr_data)
            )

        return cls(
            module_name=module_name,
            sensor_name=sensor_name,
            name_ranges=tuple(name_ranges),
            channels=channels,
            address=address,
            channel_enable=channel_enable,
            action_table=action_table,
        )


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    """Strongly-typed specification for a Velbus hardware module."""

    type_name: str = ""
    memory_map_build: str | None = None
    all_channel_status: str | None = None
    temperature_channel: str | None = None
    thermostat: str | None = None
    thermostat_addr: int | None = None
    slider_scale: int | None = None
    channels: dict[int, ChannelSpec] = field(default_factory=dict)
    properties: dict[str, PropertySpec] = field(default_factory=dict)
    command_to_class: dict[str, type[Message]] = field(default_factory=dict)
    channel_number_map: dict[str, int] = field(default_factory=dict)
    memory: MemorySpec = field(default_factory=MemorySpec)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModuleSpec:
        """Create a ModuleSpec from dictionary data."""
        # Channels
        channels: dict[int, ChannelSpec] = {}
        for chan_str, chan_data in data.get("Channels", {}).items():
            if isinstance(chan_str, int):
                chan_num = chan_str
            elif isinstance(chan_str, str):
                chan_num = (
                    int(chan_str, 16)
                    if chan_str.startswith("0x") or not chan_str.isdigit()
                    else int(chan_str)
                )
            else:
                raise ValueError(
                    f"Invalid channel number type '{type(chan_str)}' ({chan_str!r}) in spec '{data.get('Type', '')}'"
                )
            if not isinstance(chan_data, dict):
                raise ValueError(
                    f"Invalid channel data format for channel '{chan_str}' in spec '{data.get('Type', '')}'"
                )
            channels[chan_num] = ChannelSpec.from_dict(chan_data)

        # Properties
        properties: dict[str, PropertySpec] = {}
        for prop_key, prop_data in data.get("Properties", {}).items():
            if not isinstance(prop_data, dict):
                raise ValueError(
                    f"Invalid property data format for property '{prop_key}' in spec '{data.get('Type', '')}'"
                )
            properties[prop_key] = PropertySpec.from_dict(prop_key, prop_data)

        # Command to class
        command_to_class: dict[str, type[Message]] = {}
        for cmd_hex, class_val in data.get("CommandToClass", {}).items():
            if isinstance(class_val, type):
                command_to_class[cmd_hex] = class_val
            elif isinstance(class_val, str):
                cls_obj = MESSAGE_CATALOG.get(class_val)
                if cls_obj is None:
                    raise KeyError(
                        f"Unknown message class '{class_val}' for command '{cmd_hex}' in module spec '{data.get('Type', '')}'"
                    )
                command_to_class[cmd_hex] = cls_obj
            else:
                raise ValueError(
                    f"Invalid command class type '{type(class_val)}' for command '{cmd_hex}' in spec '{data.get('Type', '')}'"
                )

        # Channel number map
        channel_number_map: dict[str, int] = {}
        chan_numbers = data.get("ChannelNumbers", {})
        if isinstance(chan_numbers, dict):
            name_map = chan_numbers.get("Name", {}).get("Map", {})
            if isinstance(name_map, dict):
                for k, v in name_map.items():
                    channel_number_map[str(k).upper()] = int(v)

        # Memory
        memory_data = data.get("Memory")
        memory = (
            MemorySpec.from_dict(memory_data)
            if isinstance(memory_data, dict)
            else MemorySpec()
        )

        return cls(
            type_name=data.get("Type", ""),
            memory_map_build=data.get("MemoryMapBuild"),
            all_channel_status=data.get("AllChannelStatus"),
            temperature_channel=data.get("TemperatureChannel"),
            thermostat=data.get("Thermostat"),
            thermostat_addr=data.get("ThermostatAddr"),
            slider_scale=data.get("sliderScale"),
            channels=channels,
            properties=properties,
            command_to_class=command_to_class,
            channel_number_map=channel_number_map,
            memory=memory,
        )
