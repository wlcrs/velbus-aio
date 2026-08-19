"""Runtime-checkable protocols for polymorphic item and channel categorization."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class HasUnit(Protocol):
    """Protocol for items and channels that provide a measurement unit."""

    def get_unit(self) -> str | None:
        """Return the measurement unit."""
        ...


@runtime_checkable
class Counter(Protocol):
    """Protocol for counter items and channels providing counter state and counter unit."""

    def get_counter_state(self) -> int | float:
        """Return the current counter state or rate."""
        ...

    def get_counter_unit(self) -> str:
        """Return the unit of the counter."""
        ...


@runtime_checkable
class Temperature(Protocol):
    """Protocol for temperature sensor channels."""

    def get_unit(self) -> str:
        """Return the temperature unit (e.g. '°C')."""
        ...

    def get_state(self) -> float:
        """Return the current temperature."""
        ...

    def get_min(self) -> int | float | None:
        """Return the minimum temperature recorded."""
        ...

    def get_max(self) -> int | float | None:
        """Return the maximum temperature recorded."""
        ...


@runtime_checkable
class Pressable(Protocol):
    """Protocol for pressable channels (e.g. buttons)."""

    async def press(self) -> None:
        """Simulate a press action."""
        ...


@runtime_checkable
class HasEnergy(Protocol):
    """Protocol for channels providing energy measurement."""

    @property
    def energy(self) -> float | None:
        """Return the accumulated energy in kWh."""
        ...


@runtime_checkable
class Switchable(Protocol):
    """Protocol for switchable channels (e.g. relays)."""

    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        ...

    async def turn_on(self) -> None:
        """Turn the channel on."""
        ...

    async def turn_off(self) -> None:
        """Turn the channel off."""
        ...


@runtime_checkable
class Dimmable(Protocol):
    """Protocol for dimmable channels."""

    def get_dimmer_state(self) -> int:
        """Return the dimmer value."""
        ...

    async def set_dimmer_state(self, slider: int, transitiontime: int = 0) -> None:
        """Set the dimmer value."""
        ...


@runtime_checkable
class Cover(Protocol):
    """Protocol for cover/blind channels."""

    async def open(self) -> None:
        """Open the cover."""
        ...

    async def close(self) -> None:
        """Close the cover."""
        ...

    async def stop(self) -> None:
        """Stop the cover movement."""
        ...
