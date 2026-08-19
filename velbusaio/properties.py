"""Velbusaio property classes.

author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

from velbusaio.baseItem import BaseItem
from velbusaio.messages.memo_text import MemoTextMessage
from velbusaio.messages.module_status import PROGRAM_SELECTION
from velbusaio.messages.select_program import SelectProgramMessage

if TYPE_CHECKING:
    from velbusaio.module import Module

T = TypeVar("T")


class Property(BaseItem, Generic[T]):
    """Base class for module-level properties holding a value of type T."""

    def __init__(
        self,
        module: Module,
        name: str,
        default: T | None = None,
    ) -> None:
        """Initialize a Property."""
        super().__init__(module, name)
        self._value: T | None = default

    @property
    def value(self) -> T | None:
        """Return the current value of the property."""
        return self._value

    @value.setter
    def value(self, value: T | None) -> None:
        """Set the internal value of the property."""
        self._value = value

    async def update_value(self, value: T) -> None:
        """Update property value from the bus and notify listeners."""
        self._value = value
        await self.maybe_status_update()

    async def set(self, value: T) -> None:
        """Set the property value on the bus."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support setting a value"
        )

    def get_state(self) -> T | None:
        """Return the current state of the property."""
        return self.value

    def get_channel_number(self) -> int:
        """Return the channel number of this property (always 0)."""
        return 0

    def get_identifier(self) -> str:
        """Return the identifier of the entity."""
        return str(self.module.get_address())

    def is_sub_device(self) -> bool:
        """Return false, a property is never a subdevice."""
        return False

    def get_categories(self) -> list[str]:
        """Get the category of this property.

        default is 'sensor'.
        Override in subclass if needed.
        """
        return ["sensor"]

    def get_sensor_type(self) -> str:
        """Get the sensor type of this property.

        Override in subclass if needed.
        """
        return "none"

    def get_property_key(self) -> str:
        """Return a stable, type-unique key for use in unique_id generation."""
        return f"property_{type(self).__name__.lower()}"


class PSUPower(Property[float]):
    """PSU Power property."""

    def __init__(self, module: Module, name: str) -> None:
        """Initialize a PSUPower property."""
        super().__init__(module, name, default=0.0)

    @property
    def value(self) -> float:
        """Return the current state of the PSU power."""
        return round(self._value or 0.0, 2)


class PSUVoltage(PSUPower):
    """PSU Voltage property."""


class PSUCurrent(PSUPower):
    """PSU Current property."""


class PSULoad(PSUPower):
    """PSU Load property."""


class MemoText(Property[str]):
    """A memo text property for modules with memo text support (e.g. VMB8PBU, VMBGP*, etc.)."""

    def __init__(self, module: Module, name: str) -> None:
        """Initialize a MemoText property."""
        super().__init__(module, name, default="")

    def get_categories(self) -> list[str]:
        """The MemoText property has no categories."""
        return []

    async def set(self, value: str) -> None:
        """Set the memo text on the bus."""
        msg = self.module.create_message(
            MemoTextMessage, address=self.module.get_address()
        )
        msgcntr = 0
        current_name = ""
        for char in value:
            current_name += char
            if len(current_name) >= 5:
                msg.name = current_name
                await self.send_message(msg)
                msgcntr += 5
                msg = self.module.create_message(
                    MemoTextMessage, address=self.module.get_address()
                )
                msg.start = msgcntr
                current_name = ""
        if current_name:
            msg.name = current_name
            await self.send_message(msg)
        await self.update_value(value)


class SelectedProgram(Property[str]):
    """A selected program property."""

    def __init__(self, module: Module, name: str) -> None:
        """Initialize a SelectedProgram property."""
        super().__init__(module, name, default=None)

    def get_categories(self) -> list[str]:
        """Return the categories for this property."""
        return ["select"]

    def get_class(self) -> None:
        """Return the device class for this property."""
        return

    def get_options(self) -> list[str]:
        """Return the available program options for this property."""
        return list(PROGRAM_SELECTION.values())

    async def set(self, value: str) -> None:
        """Set the currently selected program on the bus."""
        index = list(PROGRAM_SELECTION.values()).index(value)
        program = list(PROGRAM_SELECTION.keys())[index]
        msg = self.module.create_message(
            SelectProgramMessage, address=self.module.get_address()
        )
        msg.select_program = program
        await self.send_message(msg)
        await self.update_value(value)

    def get_selected_program(self) -> str | None:
        """Return the currently selected program."""
        return self.value

    async def set_selected_program(self, program_str: str) -> None:
        """Set the currently selected program."""
        await self.set(program_str)


class LightValue(Property[float]):
    """Light value property."""

    def __init__(self, module: Module, name: str) -> None:
        """Initialize a LightValue property."""
        super().__init__(module, name, default=0.0)

    @property
    def value(self) -> float:
        """Return the current light sensor value."""
        return round(self._value or 0.0, 2)


class BusErrorTx(Property[int]):
    """Bus Error Transmit property."""

    def __init__(self, module: Module, name: str) -> None:
        """Initialize a BusErrorTx property."""
        super().__init__(module, name, default=0)

    @property
    def value(self) -> float:
        """Return the current Bus Error Transmit count."""
        return float(self._value or 0)


class BusErrorRx(BusErrorTx):
    """Bus Error Receive property."""


class BusErrorOff(BusErrorTx):
    """Bus Error OFF property."""
