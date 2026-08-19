"""Lighting domain channels (Dimmer, Relay, EdgeLit)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from velbusaio.channels import Channel
from velbusaio.config import ConfigParameter
from velbusaio.messages.cancel_forced_off import CancelForcedOff
from velbusaio.messages.cancel_forced_on import CancelForcedOn
from velbusaio.messages.cancel_inhibit import CancelInhibit
from velbusaio.messages.edge_set_color import (
    CustomColorPriority,
    SetCustomColorMessage,
    SetEdgeColorMessage,
)
from velbusaio.messages.forced_off import ForcedOff
from velbusaio.messages.forced_on import ForcedOn
from velbusaio.messages.inhibit import Inhibit
from velbusaio.messages.restore_dimmer import RestoreDimmerMessage
from velbusaio.messages.set_dimmer import SetDimmerMessage
from velbusaio.messages.switch_relay_off import SwitchRelayOffMessage
from velbusaio.messages.switch_relay_on import SwitchRelayOnMessage

if TYPE_CHECKING:
    from velbusaio.module import Module


class Dimmer(Channel):
    """A Dimmer channel."""

    state: int = 0

    def __init__(
        self,
        module: Module,
        num: int,
        name: str,
        nameEditable: bool,
        subDevice: bool,
        address: int,
        slider_scale: int = 100,
    ):
        """Initialize the dimmer channel."""
        super().__init__(module, num, name, nameEditable, subDevice, address)
        self.slider_scale = slider_scale

    async def update_dimmer_state(self, state: int) -> None:
        """Update dimmer level state."""
        self.state = state
        await self.maybe_status_update()

    def get_categories(self) -> list[str]:
        """Return the categories for this channel."""
        return ["light"]

    def is_on(self) -> bool:
        """Check if a dimmer is turned on."""
        return self.state != 0

    def get_dimmer_state(self) -> int:
        """Return the dimmer state."""
        return int(self.state * 100 / self.slider_scale)

    async def set_dimmer_state(self, slider: int, transitiontime: int = 0) -> None:
        """Set dimmer to slider."""
        msg = self.create_message(SetDimmerMessage)
        msg.dimmer_state = int(slider * self.slider_scale / 100)
        msg.dimmer_transitiontime = int(transitiontime)
        msg.dimmer_channels = [self._num]
        await self.send_message(msg)

    async def restore_dimmer_state(self, transitiontime: int = 0) -> None:
        """Restore dimmer to last known state."""
        msg = self.create_message(RestoreDimmerMessage)
        msg.dimmer_transitiontime = int(transitiontime)
        msg.dimmer_channels = [self._num]
        await self.send_message(msg)


class Relay(Channel):
    """A Relay channel."""

    on: bool | None = None
    enabled: bool = True
    inhibit: bool = False
    forced_on: bool = False
    forced_off: bool = False
    disabled: bool = False

    async def update_status(
        self,
        *,
        on: bool,
        inhibit: bool = False,
        forced_on: bool = False,
        forced_off: bool = False,
        disabled: bool = False,
    ) -> None:
        """Update full relay state."""
        self.on = on
        self.inhibit = inhibit
        self.forced_on = forced_on
        self.forced_off = forced_off
        self.disabled = disabled
        await self.maybe_status_update()

    async def set_forced_on_state(self, state: bool) -> None:
        """Update forced on state."""
        self.forced_on = state
        await self.maybe_status_update()

    async def set_forced_off_state(self, state: bool) -> None:
        """Update forced off state."""
        self.forced_off = state
        await self.maybe_status_update()

    async def set_inhibit_state(self, state: bool) -> None:
        """Update inhibit state."""
        self.inhibit = state
        await self.maybe_status_update()

    def get_categories(self) -> list[str]:
        """Return the categories for this channel."""
        if self.enabled:
            return ["switch"]
        return []

    def is_on(self) -> bool | None:
        """Return if this relay is on."""
        return self.on

    def is_inhibit(self) -> bool:
        """Return if this relay is inhibited."""
        return self.inhibit

    def is_forced_on(self) -> bool:
        """Return if this relay is forced on."""
        return self.forced_on

    def is_forced_off(self) -> bool:
        """Return if this relay is forced off."""
        return self.forced_off

    def is_disabled(self) -> bool:
        """Return if this relay is disabled."""
        return self.disabled

    def supports_inhibit(self) -> bool:
        """Return True when inhibit / cancel-inhibit commands are available."""
        return self.module.has_command(Inhibit._command_code)

    def supports_forced_on(self) -> bool:
        """Return True when forced-on / cancel-forced-on commands are available."""
        return self.module.has_command(ForcedOn._command_code)

    def supports_forced_off(self) -> bool:
        """Return True when forced-off / cancel-forced-off commands are available."""
        return self.module.has_command(ForcedOff._command_code)

    async def turn_on(self) -> None:
        """Send the turn on message."""
        msg = self.create_message(SwitchRelayOnMessage)
        msg.relay_channels = [self._num]
        await self.send_message(msg)

    async def turn_off(self) -> None:
        """Send the turn off message."""
        msg = self.create_message(SwitchRelayOffMessage)
        msg.relay_channels = [self._num]
        await self.send_message(msg)

    async def set_forced_on(self, state: bool) -> None:
        """Set or cancel forced on."""
        msg = self.create_message(ForcedOn if state else CancelForcedOn)
        msg.channel = self._num
        if state:
            msg.delay_time = 0xFFFFFF  # Permanent
        await self.send_message(msg)

    async def set_forced_off(self, state: bool) -> None:
        """Set or cancel forced off."""
        msg = self.create_message(ForcedOff if state else CancelForcedOff)
        msg.channel = self._num
        if state:
            msg.delay_time = 0xFFFFFF  # Permanent
        await self.send_message(msg)

    async def set_inhibit(self, state: bool) -> None:
        """Set or cancel inhibit."""
        msg = self.create_message(Inhibit if state else CancelInhibit)
        msg.channel = self._num
        if state:
            msg.delay_time = 0xFFFFFF  # Permanent
        await self.send_message(msg)

    async def get_normal_closed(self, *, refresh: bool = False) -> bool | None:
        """Return True when this relay is programmed as normally closed."""
        table = self.get_action_table()
        if table is None:
            return None
        return await table.get_normal_closed(refresh=refresh)

    async def set_normal_closed(self, normal_closed: bool) -> None:
        """Program NO/NC contact behaviour in EEPROM."""
        table = self.get_action_table()
        if table is None:
            raise RuntimeError(f"Channel {self._num} has no action table")
        await table.set_normal_closed(normal_closed)

    def get_config_parameters(self) -> list[ConfigParameter]:
        """Return discoverable CONFIG parameters for this relay channel."""
        params: list[ConfigParameter] = [
            ConfigParameter(
                key="name",
                label="Channel name",
                kind="text",
                getter=self._get_name_value,
                setter=self.set_name_persistent,
                max_length=16,
                channel=self._num,
                entity=False,
            ),
        ]
        if self.supports_inhibit():
            params.append(
                ConfigParameter(
                    key="inhibit",
                    label="Inhibit",
                    kind="bool",
                    getter=self._get_inhibit_value,
                    setter=self.set_inhibit,
                    channel=self._num,
                )
            )
        if self.supports_forced_on():
            params.append(
                ConfigParameter(
                    key="forced_on",
                    label="Forced on",
                    kind="bool",
                    getter=self._get_forced_on_value,
                    setter=self.set_forced_on,
                    channel=self._num,
                )
            )
        if self.supports_forced_off():
            params.append(
                ConfigParameter(
                    key="forced_off",
                    label="Forced off",
                    kind="bool",
                    getter=self._get_forced_off_value,
                    setter=self.set_forced_off,
                    channel=self._num,
                )
            )
        table = self.get_action_table()
        if table is not None and table.noc_address is not None:
            params.append(
                ConfigParameter(
                    key="contact",
                    label="Contact",
                    kind="select",
                    getter=self._get_contact_value,
                    setter=self._set_contact_value,
                    options=["NO", "NC"],
                    channel=self._num,
                    entity=False,
                )
            )
        return params

    async def _get_name_value(self) -> str:
        return self.name

    async def _get_inhibit_value(self) -> bool:
        return self.is_inhibit()

    async def _get_forced_on_value(self) -> bool:
        return self.is_forced_on()

    async def _get_forced_off_value(self) -> bool:
        return self.is_forced_off()

    async def _get_contact_value(self) -> str:
        normal_closed = await self.get_normal_closed()
        if normal_closed is None:
            return "NO"
        return "NC" if normal_closed else "NO"

    async def _set_contact_value(self, value: str) -> None:
        await self.set_normal_closed(str(value).upper() == "NC")


class EdgeLit(Channel):
    """An EdgeLit channel."""

    def get_categories(self) -> list[str]:
        """Return the categories for this channel."""
        return ["light"]

    async def reset_color(self, left=True, top=True, right=True, bottom=True):
        """Send the edgelit color message."""
        msg = self.create_message(SetEdgeColorMessage)
        msg.apply_background_color = True
        msg.color_idx = 0
        msg.apply_to_left_edge = left
        msg.apply_to_top_edge = top
        msg.apply_to_right_edge = right
        msg.apply_to_bottom_edge = bottom
        msg.apply_to_all_pages = True
        await self.send_message(msg)

    async def set_color(
        self,
        color_idx: int,
        left=True,
        top=True,
        right=True,
        bottom=True,
        blinking=False,
        priority=CustomColorPriority.LOW_PRIORITY,
    ) -> None:
        """Send the set color message."""
        msg = self.create_message(SetEdgeColorMessage)
        msg.apply_background_color = True
        msg.background_blinking = blinking
        msg.color_idx = color_idx
        msg.apply_to_left_edge = left
        msg.apply_to_top_edge = top
        msg.apply_to_right_edge = right
        msg.apply_to_bottom_edge = bottom
        msg.apply_to_all_pages = True
        msg.custom_color_priority = priority
        await self.send_message(msg)

    async def set_rgbw(
        self,
        red: int,
        green: int,
        blue: int,
        white: int,
        left=False,
        top=False,
        right=False,
        bottom=False,
    ) -> None:
        """Set RGBW color for specific edges using a dedicated palette index per side."""
        if left:
            palette_idx = 1
        elif top:
            palette_idx = 2
        elif right:
            palette_idx = 3
        elif bottom:
            palette_idx = 4
        else:
            return

        if red == 0 and green == 0 and blue == 0 and white == 0:
            msg_apply = self.create_message(SetEdgeColorMessage)
            msg_apply.apply_background_color = True
            msg_apply.custom_color_palette = False
            msg_apply.color_idx = 0
            msg_apply.apply_to_left_edge = left
            msg_apply.apply_to_top_edge = top
            msg_apply.apply_to_right_edge = right
            msg_apply.apply_to_bottom_edge = bottom
            msg_apply.apply_to_all_pages = True
            await self.send_message(msg_apply)
            return

        msg_palette = self.create_message(SetCustomColorMessage)
        msg_palette.palette_idx = palette_idx
        msg_palette.red = red
        msg_palette.green = green
        msg_palette.blue = blue
        msg_palette.white_mode = white > 128
        msg_palette.saturation = 127
        await self.send_message(msg_palette)

        msg_apply = self.create_message(SetEdgeColorMessage)
        msg_apply.apply_background_color = True
        msg_apply.custom_color_palette = True
        msg_apply.color_idx = palette_idx
        msg_apply.apply_to_left_edge = left
        msg_apply.apply_to_top_edge = top
        msg_apply.apply_to_right_edge = right
        msg_apply.apply_to_bottom_edge = bottom
        msg_apply.apply_to_all_pages = True
        await self.send_message(msg_apply)
