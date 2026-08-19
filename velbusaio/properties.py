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
        self.value: T | None = default

    async def update_value(self, value: T) -> None:
        """Update property value from the bus and notify listeners."""
        self.value = value
        await self.maybe_status_update()

    async def set(self, value: T) -> None:
        """Set the property value on the bus."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support setting a value"
        )

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

    @property
    def property_key(self) -> str:
        """Return a stable, type-unique key for use in unique_id generation."""
        return f"property_{type(self).__name__.lower()}"


class PSUPower(Property[float]):
    """PSU Power property."""

    def __init__(self, module: Module, name: str) -> None:
        """Initialize a PSUPower property."""
        super().__init__(module, name, default=0.0)

    async def update_value(self, value: float) -> None:
        """Update PSU power value and notify listeners."""
        self.value = round(value or 0.0, 2)
        await self.maybe_status_update()


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
            MemoTextMessage, address=self.module.address
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
                    MemoTextMessage, address=self.module.address
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

    @property
    def options(self) -> list[str]:
        """Return the available program options for this property."""
        return list(PROGRAM_SELECTION.values())

    async def set(self, value: str) -> None:
        """Set the currently selected program on the bus."""
        index = list(PROGRAM_SELECTION.values()).index(value)
        program = list(PROGRAM_SELECTION.keys())[index]
        msg = self.module.create_message(
            SelectProgramMessage, address=self.module.address
        )
        msg.select_program = program
        await self.send_message(msg)
        await self.update_value(value)


class LightValue(Property[float]):
    """Light value property."""

    def __init__(self, module: Module, name: str) -> None:
        """Initialize a LightValue property."""
        super().__init__(module, name, default=0.0)

    async def update_value(self, value: float) -> None:
        """Update light value and notify listeners."""
        self.value = round(value or 0.0, 2)
        await self.maybe_status_update()


class BusErrorTx(Property[int]):
    """Bus Error Transmit property."""

    def __init__(self, module: Module, name: str) -> None:
        """Initialize a BusErrorTx property."""
        super().__init__(module, name, default=0)

    async def update_value(self, value: int) -> None:
        """Update bus error count and notify listeners."""
        self.value = float(value or 0)
        await self.maybe_status_update()


class BusErrorRx(BusErrorTx):
    """Bus Error Receive property."""


class BusErrorOff(BusErrorTx):
    """Bus Error OFF property."""
