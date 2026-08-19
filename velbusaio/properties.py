"""Velbusaio property classes.

author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Generic, TypeVar

from velbusaio.baseItem import BaseItem
from velbusaio.message import Message
from velbusaio.messages.memo_text import MemoTextMessage
from velbusaio.messages.module_status import PROGRAM_SELECTION
from velbusaio.messages.select_program import SelectProgramMessage

if TYPE_CHECKING:
    from velbusaio.module import Module

T = TypeVar("T")


class Property(BaseItem, Generic[T]):
    """Base class for module-level properties holding a value of type T."""

    cur: T | None = None

    def __init__(
        self,
        module: Module,
        name: str,
        writer: Callable[[Message], Awaitable[None]],
        default: T | None = None,
    ) -> None:
        super().__init__(module, name, writer)
        self.cur = default

    async def update_value(self, cur: T) -> None:
        """Update property value."""
        self.cur = cur
        await self.maybe_status_update()

    def get_state(self) -> T | None:
        """Return the current state of the property."""
        return self.cur

    def get_channel_number(self) -> int:
        """Return the channel number of this property (always 0)."""
        return 0

    def get_identifier(self) -> str:
        """Return the identifier of the entity."""
        return str(self.get_module_address())

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
        return type(self).__name__

    def get_property_key(self) -> str:
        """Return a stable, type-unique key for use in unique_id generation."""
        return type(self).__name__


class PSUPower(Property[float]):
    """PSU Power property."""

    def __init__(
        self, module: Module, name: str, writer: Callable[[Message], Awaitable[None]]
    ) -> None:
        super().__init__(module, name, writer, default=0.0)

    def get_state(self) -> float:
        """Return the current state of the PSU power."""
        return round(self.cur or 0.0, 2)


class PSUVoltage(PSUPower):
    """PSU Voltage property."""


class PSUCurrent(PSUPower):
    """PSU Current property."""


class PSULoad(PSUPower):
    """PSU Load property."""


class MemoText(Property[str]):
    """Memo text property."""

    def get_categories(self) -> list[str]:
        """The MemoText property has no categories."""
        return []

    async def set(self, txt: str) -> None:
        """Set the memo text."""
        msg = self._module.create_message(
            MemoTextMessage, address=self.get_module_address()
        )
        msgcntr = 0
        current_name = ""
        for char in txt:
            current_name += char
            if len(current_name) >= 5:
                msg.name = current_name
                await self._writer(msg)
                msgcntr += 5
                msg = self._module.create_message(
                    MemoTextMessage, address=self.get_module_address()
                )
                msg.start = msgcntr
                current_name = ""
        if current_name:
            msg.name = current_name
            await self._writer(msg)


class SelectedProgram(Property[str]):
    """A selected program property."""

    def __init__(
        self, module: Module, name: str, writer: Callable[[Message], Awaitable[None]]
    ) -> None:
        super().__init__(module, name, writer, default=None)

    def get_categories(self) -> list[str]:
        """Return the categories for this property."""
        return ["select"]

    def get_class(self) -> None:
        """Return the device class for this property."""
        return

    def get_options(self) -> list[str]:
        """Return the available program options for this property."""
        return list(PROGRAM_SELECTION.values())

    def get_selected_program(self) -> str | None:
        """Return the currently selected program."""
        return self.cur

    async def set_selected_program(self, program_str: str) -> None:
        """Set the currently selected program."""
        index = list(PROGRAM_SELECTION.values()).index(program_str)
        program = list(PROGRAM_SELECTION.keys())[index]
        msg = self._module.create_message(
            SelectProgramMessage, address=self.get_module_address()
        )
        msg.select_program = program
        await self._writer(msg)
        await self.update_value(program_str)


class LightValue(Property[float]):
    """Light value property."""

    def __init__(
        self, module: Module, name: str, writer: Callable[[Message], Awaitable[None]]
    ) -> None:
        super().__init__(module, name, writer, default=0.0)

    def get_state(self) -> float:
        """Return the current light sensor value."""
        return round(self.cur or 0.0, 2)


class BusErrorTx(Property[int]):
    """Bus Error Transmit property."""

    def __init__(
        self, module: Module, name: str, writer: Callable[[Message], Awaitable[None]]
    ) -> None:
        super().__init__(module, name, writer, default=0)

    def get_state(self) -> float:
        """Return the current Bus Error Transmit count."""
        return float(self.cur or 0)


class BusErrorRx(BusErrorTx):
    """Bus Error Receive property."""


class BusErrorOff(BusErrorTx):
    """Bus Error OFF property."""
