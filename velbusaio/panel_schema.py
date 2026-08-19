"""Derive Velbus config panel UI schema from module specifications."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from velbusaio.actions import iter_action_options
from velbusaio.module_spec import ModuleSpec
from velbusaio.module_spec_loader import load_module_spec

if TYPE_CHECKING:
    from velbusaio.module import Module


def _channel_entries(spec: ModuleSpec) -> list[dict[str, Any]]:
    enable_channels = set(
        spec.memory.channel_enable.channels
        if spec.memory.channel_enable
        else ()
    )
    entries: list[dict[str, Any]] = []
    for channel, chan_spec in sorted(spec.channels.items(), key=lambda item: item[0]):
        entries.append(
            {
                "channel": channel,
                "name": chan_spec.name or f"Channel {channel}",
                "type": chan_spec.channel_type,
                "editable": chan_spec.editable,
                "subdevice": chan_spec.subdevice,
                "supports_enable": channel in enable_channels,
            }
        )
    return entries


def _channel_enable_section(spec: ModuleSpec) -> dict[str, Any] | None:
    enable = spec.memory.channel_enable
    if not enable:
        return None
    channels = sorted(enable.channels.keys())
    if not channels:
        return None
    return {
        "id": "channel_enable",
        "type": "channel_enable",
        "channels": channels,
    }


def _contact_section(spec: ModuleSpec) -> dict[str, Any] | None:
    action_table = spec.memory.action_table
    if not action_table:
        return None
    channels = sorted(
        channel
        for channel, chan_spec in action_table.channels.items()
        if chan_spec.noc_address is not None
    )
    if not channels:
        return None
    return {
        "id": "contact",
        "type": "contact",
        "channels": channels,
        "options": ["NO", "NC"],
    }


def _editable_name_channels(spec: ModuleSpec) -> list[dict[str, Any]]:
    editable = {
        chan_num
        for chan_num, chan_spec in spec.channels.items()
        if chan_spec.editable and chan_num in spec.memory.channels
    }
    return [entry for entry in _channel_entries(spec) if entry["channel"] in editable]


def _action_table_section(spec: ModuleSpec) -> dict[str, Any] | None:
    action_table = spec.memory.action_table
    if not action_table:
        return None
    catalog_id = action_table.actions or "relay_classic"
    channels = sorted(int(key) for key in action_table.channels)
    kind = (
        action_table.kind
        or ("input" if catalog_id.startswith("input_") else "output")
    )
    return {
        "id": "action_table",
        "type": "action_table",
        "kind": kind,
        "catalog_id": catalog_id,
        "slot_count": action_table.slot_count or 39,
        "slot_size": action_table.slot_size or 6,
        "layout": action_table.layout or "per_channel",
        "channels": channels,
        "actions": list(iter_action_options(catalog_id)),
    }


def _properties_section(spec: ModuleSpec) -> dict[str, Any] | None:
    if not spec.properties:
        return None
    items: list[dict[str, Any]] = []
    for key, prop_spec in spec.properties.items():
        if not prop_spec.prop_type:
            continue
        items.append(
            {
                "key": key,
                "name": prop_spec.name,
                "property_type": prop_spec.prop_type,
            }
        )
    if not items:
        return None
    return {"id": "properties", "type": "properties", "properties": items}


def get_module_type_schema(type_id: int) -> dict[str, Any]:
    """Return the panel schema for a module type."""
    spec = load_module_spec(type_id)
    sections: list[dict[str, Any]] = []

    channels = _channel_entries(spec)
    if channels:
        sections.append({"id": "channels", "type": "channels", "channels": channels})

    name_channels = _editable_name_channels(spec)
    if name_channels:
        sections.append(
            {
                "id": "channel_names",
                "type": "channel_names",
                "channels": name_channels,
            }
        )

    contact_section = _contact_section(spec)
    if contact_section is not None:
        sections.append(contact_section)

    enable_section = _channel_enable_section(spec)
    if enable_section is not None:
        sections.append(enable_section)

    action_section = _action_table_section(spec)
    if action_section is not None:
        sections.append(action_section)

    properties_section = _properties_section(spec)
    if properties_section is not None:
        sections.append(properties_section)

    return {
        "type_id": type_id,
        "type_name": spec.type_name or f"0x{type_id:02X}",
        "sections": sections,
    }


async def get_module_instance_data(module: Module) -> dict[str, Any]:
    """Return live module values for the config panel."""
    channels = module.channels
    channel_data: dict[str, Any] = {}
    for channel_num, channel in channels.items():
        entry: dict[str, Any] = {
            "name": channel.name,
            "type": type(channel).__name__,
        }
        if (
            hasattr(channel, "supports_channel_enable")
            and channel.supports_channel_enable()
        ):
            entry["enabled"] = await channel.get_channel_enabled()
        elif hasattr(channel, "is_enabled"):
            entry["enabled"] = channel.is_enabled()
        table = (
            channel.action_table if hasattr(channel, "action_table") else None
        )
        if table is not None and table.noc_address is not None:
            normal_closed = await channel.get_normal_closed()
            if normal_closed is not None:
                entry["contact"] = "NC" if normal_closed else "NO"
        channel_data[str(channel_num)] = entry

    properties: dict[str, Any] = {}
    for key, prop in module.properties.items():
        if hasattr(prop, "value"):
            properties[key] = prop.value
        elif hasattr(prop, "get_state"):
            properties[key] = prop.get_state()

    return {
        "address": module.addresses[0],
        "name": module.name,
        "type_id": module.type,
        "type_name": module.type_name,
        "serial": module.serial,
        "sw_version": module.sw_version,
        "channels": channel_data,
        "properties": properties,
    }
