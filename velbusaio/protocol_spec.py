from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProtocolMessageSpec:
    """Specification for a special protocol message (e.g. broadcast, ignore)."""

    command: int
    name: str
    priority: str = "Low"
    info: str | None = None

    @property
    def command_hex(self) -> str:
        """Hexadecimal string representation of command."""
        return f"{self.command:02X}"

    def __getitem__(self, key: str) -> Any:
        if key == "Name":
            return self.name
        if key == "Prio":
            return self.priority
        if key == "Info":
            return self.info
        raise KeyError(key)

    @classmethod
    def from_dict(cls, cmd_hex: str, data: dict[str, Any]) -> ProtocolMessageSpec:
        """Create a ProtocolMessageSpec from dictionary data."""
        return cls(
            command=int(cmd_hex, 16),
            name=data.get("Name", ""),
            priority=data.get("Prio", "Low"),
            info=data.get("Info"),
        )
