"""BaseItem base class for Velbusaio properties and channels.

author: Maikel Punie <maikel.punie@gmail.com>
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, final

from velbusaio.message import Message

if TYPE_CHECKING:
    from velbusaio.module import Module

_MISSING = object()


class DirtyTrackingMixin:
    """Mixin providing automatic dirty state tracking for annotated public attributes."""

    _tracked_fields: frozenset[str] = frozenset()
    _is_dirty: bool = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        tracked: set[str] = set()
        for base in cls.__mro__:
            for attr in getattr(base, "__annotations__", {}):
                if not attr.startswith("_"):
                    tracked.add(attr)
        cls._tracked_fields = frozenset(tracked)

    def __setattr__(self, name: str, value: Any) -> None:
        if hasattr(self, "_tracked_fields") and name in self._tracked_fields:
            current_value = getattr(self, name, _MISSING)
            if current_value != value:
                super().__setattr__("_is_dirty", True)
        super().__setattr__(name, value)


class BaseItem(DirtyTrackingMixin, ABC):
    """Base class for properties or channels."""

    def __init__(
        self,
        module: Module,
        name: str,
    ):
        """Initialize the property or channel."""
        self.module = module
        self.name = name
        self.default_name = name
        self._on_status_update: list[Callable[[], Awaitable[None]]] = []
        self._is_dirty = False

    @final
    async def send_message(self, message: Message) -> None:
        """Send a message through the parent module."""
        if self.module is None:
            raise RuntimeError(f"Item {self.name} has no module associated")
        await self.module.send_message(message)

    @final
    @property
    def full_name(self) -> str:
        """Return full channel name including module name and type."""
        if self.is_sub_device():
            return f"{self.module.get_name()} ({self.module.get_type_name()}) - {self.name}"
        return f"{self.module.get_name()} ({self.module.get_type_name()})"

    @final
    def __repr__(self) -> str:
        """Representation of this property."""
        items = []
        for k, v in self.__dict__.items():
            if k not in ["module", "_class", "_on_status_update", "_is_dirty"]:
                items.append(f"{k} = {v!r}")
        return "{}[{}]".format(type(self), ", ".join(items))

    @final
    def __str__(self) -> str:
        """String representation of this property."""
        return self.__repr__()

    @abstractmethod
    def get_categories(self) -> list[str]:
        """Get the category of this property."""

    @abstractmethod
    def get_sensor_type(self) -> str | None:
        """Get the sensor type of this property."""

    @abstractmethod
    def is_sub_device(self) -> bool:
        """Return if this item is a subdevice."""

    @abstractmethod
    def get_identifier(self) -> str:
        """Return a unique identifier for this property."""

    @abstractmethod
    def get_channel_number(self) -> int:
        """Return the channel number of this item."""

    @final
    def to_cache(self) -> dict:
        """Return a cacheable representation of this property.

        By default, all instance attributes except internal references
        like the parent module and callbacks are included.
        """
        data: dict = {}
        for key, value in self.__dict__.items():
            if key in ("module", "_on_status_update", "_writer", "_is_dirty"):
                continue
            data[key] = value
        return data

    @final
    async def maybe_status_update(self) -> None:
        """Call all registered status update methods if any tracked attributes have changed."""
        if self._is_dirty:
            self._is_dirty = False
            await self.status_update()

    @final
    async def status_update(self) -> None:
        """Call all registered status update methods."""
        for m in self._on_status_update:
            await m()

    @final
    def on_status_update(self, meth: Callable[[], Awaitable[None]]) -> None:
        """Register a method to be called on status update."""
        self._on_status_update.append(meth)

    @final
    def remove_on_status_update(self, meth: Callable[[], Awaitable[None]]) -> None:
        """Remove a method from the status update callbacks."""
        self._on_status_update.remove(meth)

    @final
    def get_info(self) -> dict[str, Any]:
        """Get the channel info as a dictionary."""
        data = {}
        data["type"] = self.__class__.__name__
        for key, value in self.__dict__.items():
            if key not in [
                "module",
                "_writer",
                "_name_parts",
                "_on_status_update",
                "_is_dirty",
            ]:
                data[key.lstrip("_")] = value
        return data

    def get_unit(self) -> str | None:
        """Return the unit of the counter."""
        return None

    def get_counter_state(self) -> int:
        """Return the current state of the counter."""
        return 0

    def get_counter_unit(self) -> str:
        """Return the unit of the counter."""
        return ""

    def is_temperature(self) -> bool:
        """Return if this item is a temperature sensor."""
        return False

    def is_counter_channel(self) -> bool:
        """Return if this item is a counter channel."""
        return False
