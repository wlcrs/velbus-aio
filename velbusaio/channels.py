"""Velbusaio channel classes.

author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

import string
from typing import TYPE_CHECKING, Any

from velbusaio.baseItem import BaseItem
from velbusaio.config import decode_name, encode_name
from velbusaio.message import Message

if TYPE_CHECKING:
    from velbusaio.actions import ActionSlot
    from velbusaio.module import Module


class Channel(BaseItem):
    """A velbus channel.

    This is the basic abstract class of a velbus channel
    Each specific channel type (Relay, Dimmer, Temperature, etc.) will inherit from this class
    and implement its own specific methods and attributes.
    """

    def __init__(
        self,
        module: Module,
        num: int,
        name: str,
        nameEditable: bool,
        subDevice: bool,
        address: int,
    ):
        """Initialize the channel."""
        super().__init__(module, name)
        self._num = num
        self._subDevice = subDevice
        self._address = address
        self._name_parts = {}

    def get_identifier(self) -> str:
        """Return the identifier of the entity."""
        if not self.is_sub_device():
            return str(self._address)
        return f"{self._address}-{self.get_channel_number()}"

    def get_channel_number(self) -> int:
        """Return channel number."""
        return self._num

    def create_message[M: Message](
        self,
        message_cls: type[M],
        address: int | None = None,
    ) -> M:
        """Create the correct module-specific Message variant for this channel."""
        target_addr = self._address if address is None else address
        return self.module.create_message(message_cls, address=target_addr)

    def set_sub_device(self, sub_device: bool) -> None:
        """Set if this channel is a subdevice."""
        self._subDevice = sub_device

    def is_sub_device(self) -> bool:
        """Return if this channel is a subdevice."""
        return self._subDevice

    def set_name_char(self, pos: int, char: int) -> None:
        """Set a char of the channel name."""
        self._name_parts = {}
        while len(self.name) < int(pos):
            self.name += " "
        self.name = self.name[: int(pos)] + chr(char) + self.name[int(pos) + 1 :]

    def set_name_part(self, part: int, name: str) -> bool:
        """Set a part of the channel name. Returns True if name is now complete."""
        self._name_parts[int(part)] = name
        if len(self._name_parts) == 3:
            self._generate_name()
            return True
        return False

    def _generate_name(self) -> None:
        """Generate the channel name if all 3 parts are received."""
        name = self._name_parts[1] + self._name_parts[2] + self._name_parts[3]
        self.name = "".join(filter(lambda x: x in string.printable, name))
        self._name_parts = {}

    async def set_name_persistent(self, name: str) -> None:
        """Write channel name into module EEPROM and update the local name."""
        memory = self.module.get_memory()
        if memory is None:
            raise RuntimeError("Module memory backend is not initialized")
        name_range = self.module._channel_name_range(self._num)
        if name_range is None:
            raise ValueError(f"Channel {self._num} has no name memory range")
        start, length = name_range
        encoded = encode_name(name, length)
        await memory.write_bytes(start, encoded)
        self.name = decode_name(encoded)
        await self.module._controller.save_module_cache(self.module)  # noqa: SLF001

    def to_cache(self) -> dict:
        """Get channel state for caching."""
        dst = {
            "name": self.name,
            "type": type(self).__name__,
            "subdevice": self._subDevice,
        }
        if getattr(self, "Unit", None) is not None:
            dst["Unit"] = self.Unit
        return dst

    def __repr__(self) -> str:
        """Representation of this channel."""
        items = []
        for k, v in self.__dict__.items():
            if k not in ["module", "_writer", "_name_parts", "_class"]:
                items.append(f"{k} = {v!r}")
        return "{}[{}]".format(type(self), ", ".join(items))

    def __str__(self) -> str:
        """String representation of this channel."""
        return self.__repr__()

    def get_channel_info(self) -> dict[str, Any]:
        """Get the channel info as a dictionary."""
        data = {}
        data["type"] = self.__class__.__name__
        for key, value in self.__dict__.items():
            if key not in [
                "_module",
                "_writer",
                "_name_parts",
                "_on_status_update",
                "_is_dirty",
            ]:
                data[key.lstrip("_")] = value
        return data

    def get_categories(self) -> list[str]:
        """Get the categories (mainly for home-assistant)."""
        return []

    def get_sensor_type(self) -> str | None:
        """Return the sensor type."""
        return None

    def get_action_table(self):
        """Return this channel's action table, if available."""
        return self.module.get_action_table(self._num)

    async def get_actions(
        self, *, refresh: bool = False, include_empty: bool = False
    ) -> list[ActionSlot]:
        """Return programmed input→output action slots for this channel."""
        table = self.get_action_table()
        if table is None:
            return []
        return await table.get_actions(refresh=refresh, include_empty=include_empty)

    async def set_action(
        self,
        *,
        source_address: int,
        action: str | int,
        source_channel: int | None = None,
        source_bit: int | None = None,
        time1: int = 0xFF,
        time2: int = 0xFF,
        time3: int = 0xFF,
        time4: int = 0xFF,
        on_release: bool = False,
        slot: int | None = None,
    ) -> ActionSlot:
        """Program an input→output action on this channel."""
        table = self.get_action_table()
        if table is None:
            raise RuntimeError(f"Channel {self._num} has no action table")
        return await table.set_action(
            source_address=source_address,
            action=action,
            source_channel=source_channel,
            source_bit=source_bit,
            time1=time1,
            time2=time2,
            time3=time3,
            time4=time4,
            on_release=on_release,
            slot=slot,
        )

    async def clear_action(self, slot: int) -> ActionSlot:
        """Clear one action slot on this channel."""
        table = self.get_action_table()
        if table is None:
            raise RuntimeError(f"Channel {self._num} has no action table")
        return await table.clear_action(slot)

    async def clear_actions_for_source(
        self,
        source_address: int,
        *,
        source_channel: int | None = None,
        source_bit: int | None = None,
    ) -> list[ActionSlot]:
        """Clear action slots matching a source input."""
        table = self.get_action_table()
        if table is None:
            return []
        return await table.clear_actions_for_source(
            source_address,
            source_channel=source_channel,
            source_bit=source_bit,
        )


def __getattr__(name: str) -> Any:
    if name in ("Temperature", "ThermostatChannel"):
        import velbusaio.domains.climate.channel as mod  # noqa: PLC0415

        return getattr(mod, name)
    if name in ("Blind", "BlindState"):
        import velbusaio.domains.cover.channel as mod  # noqa: PLC0415

        return getattr(mod, name)
    if name in (
        "Button",
        "ButtonCounter",
        "ButtonLedState",
        "CounterChannel",
        "Sensor",
        "SensorNumber",
    ):
        import velbusaio.domains.input.channel as mod  # noqa: PLC0415

        return getattr(mod, name)
    if name in ("Dimmer", "EdgeLit", "Relay"):
        import velbusaio.domains.lighting.channel as mod  # noqa: PLC0415

        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Blind",
    "BlindState",
    "Button",
    "ButtonCounter",
    "ButtonLedState",
    "Channel",
    "CounterChannel",
    "Dimmer",
    "EdgeLit",
    "Relay",
    "Sensor",
    "SensorNumber",
    "Temperature",
    "ThermostatChannel",
]
