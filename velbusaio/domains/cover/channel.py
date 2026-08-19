"""Cover domain channels (Blind)."""

from __future__ import annotations

from velbusaio.channels import Channel
from velbusaio.const import BlindState
from velbusaio.messages.cover_down import CoverDownMessage
from velbusaio.messages.cover_off import CoverOffMessage
from velbusaio.messages.cover_position import CoverPosMessage
from velbusaio.messages.cover_up import CoverUpMessage


class Blind(Channel):
    """A blind channel."""

    state: BlindState | None = None
    # State reports the direction of movement: moving up, moving down or stopped
    position: int | None = None
    # Position reporting is not supported by VMBxBL modules (only in BLE/BLS)

    async def update_status(
        self, state: int | BlindState, position: int | None = None
    ) -> None:
        """Update blind movement state and optional position."""
        self.state = BlindState(state) if isinstance(state, int) else state
        if position is not None:
            self.position = position
        await self.maybe_status_update()

    def get_categories(self) -> list[str]:
        """Return the categories for this channel."""
        return ["cover"]

    def is_opening(self) -> bool:
        """Return if the blind is opening."""
        return self.state == BlindState.OPENING

    def is_closing(self) -> bool:
        """Return if the blind is closing."""
        return self.state == BlindState.CLOSING

    def is_stopped(self) -> bool:
        """Return if the blind is stopped."""
        return self.state == BlindState.STOPPED

    def is_closed(self) -> bool | None:
        """Report if the blind is fully closed."""
        if self.position is None:
            return None
        return self.position == 100

    def is_open(self) -> bool | None:
        """Report if the blind is fully open."""
        if self.position is None:
            return None
        return self.position == 0

    def support_position(self) -> bool:
        """Return if position reporting is supported."""
        return self.position is not None

    async def open(self) -> None:
        """Open the blind."""
        msg = self.create_message(CoverUpMessage)
        msg.channel = self._num
        await self.send_message(msg)

    async def close(self) -> None:
        """Close the blind."""
        msg = self.create_message(CoverDownMessage)
        msg.channel = self._num
        await self.send_message(msg)

    async def stop(self) -> None:
        """Stop the blind."""
        msg = self.create_message(CoverOffMessage)
        msg.channel = self._num
        await self.send_message(msg)

    async def set_position(self, position: int) -> None:
        """Set the blind to a specific position."""
        if position == 100:
            await self.close()
            return
        msg = self.create_message(CoverPosMessage)
        msg.channel = self._num
        msg.position = position
        await self.send_message(msg)
