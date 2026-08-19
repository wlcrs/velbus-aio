"""VmbDali module implementation for Velbus DALI devices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from velbusaio.channels import Channel, Dimmer
from velbusaio.command_registry import commandRegistry
from velbusaio.const import PRIORITY_LOW

if TYPE_CHECKING:
    from velbusaio.controller import Controller
from velbusaio.message import Message
from velbusaio.messages.channel_name_request import (
    COMMAND_CODE as CHANNEL_NAME_REQUEST_COMMAND_CODE,
)
from velbusaio.messages.clear_led import ClearLedMessage
from velbusaio.messages.dali_device_settings import (
    DaliDeviceSettingMsg,
    DeviceType as DaliDeviceType,
    DeviceTypeMsg as DaliDeviceTypeMsg,
    MemberOfGroupMsg,
)
from velbusaio.messages.dali_device_settings_request import (
    COMMAND_CODE as DALI_DEVICE_SETTINGS_REQUEST_COMMAND_CODE,
    DaliDeviceSettingsRequest,
)
from velbusaio.messages.dali_dim_value_status import DimValueStatus
from velbusaio.messages.fast_blinking_led import FastBlinkingLedMessage
from velbusaio.messages.push_button_status import PushButtonStatusMessage
from velbusaio.messages.set_led import SetLedMessage
from velbusaio.messages.slow_blinking_led import SlowBlinkingLedMessage
from velbusaio.module import Module


class VmbDali(Module):
    """DALI has a variable number of channels.

    Therefore we create a module that first creates 64 placeholder channels.
    After that it requests the DALI device settings to determine the actual channels.
    """

    def __init__(
        self,
        module_address: int,
        module_type: int,
        *,
        controller: Controller,
        serial: int | str | None = None,
        memorymap: int | None = None,
        build_year: int | None = None,
        build_week: int | None = None,
    ) -> None:
        """Initialize DALI module."""
        super().__init__(
            module_address,
            module_type,
            controller=controller,
            serial=serial,
            memorymap=memorymap,
            build_year=build_year,
            build_week=build_week,
        )
        self.group_members: dict[int, set[int]] = {}

    def get_initial_timeout(self) -> int:
        """Get initial timeout for loading this module."""
        return 100000

    def _initialize_channels(self) -> None:
        for chan in range(1, 64 + 1):
            self._channels[chan] = Channel(
                module=self,
                num=chan,
                name="placeholder",
                nameEditable=True,
                subDevice=True,
                address=self._address,
            )

    async def _request_channel_name(self) -> None:
        """Request DALI channels on bus load."""
        await self._request_dali_channels()

    async def _request_dali_channels(self) -> None:
        msg_type = commandRegistry.get_command(
            DALI_DEVICE_SETTINGS_REQUEST_COMMAND_CODE, self.get_type()
        )
        msg: DaliDeviceSettingsRequest = msg_type(self._address)
        msg.priority = PRIORITY_LOW
        msg.channel = 81  # all
        msg.settings = None  # all
        await self.send_message(msg)

    async def on_message(self, message: Message) -> None:
        """Process received message."""
        if isinstance(message, DaliDeviceSettingMsg):
            if isinstance(message.data, DaliDeviceTypeMsg):
                if message.data.device_type == DaliDeviceType.NoDevicePresent:
                    if message.channel in self._channels:
                        del self._channels[message.channel]
                # Any present DALI device (LedModule, Dimmer, and the other
                # lamp types) is exposed as a dimmable channel. Only
                # NoDevicePresent slots are removed above.
                elif self._channels.get(message.channel).__class__ != Dimmer:
                    # New or changed type, replace channel:
                    self._channels[message.channel] = Dimmer(
                        self,
                        message.channel,
                        "",
                        True,
                        True,
                        self._address,
                        slider_scale=254,
                    )
                    await self._request_single_channel_name(message.channel)

            elif isinstance(message.data, MemberOfGroupMsg):
                for group in range(15 + 1):
                    this_group_members = self.group_members.setdefault(group, set())
                    if message.data.member_of_group[group]:
                        this_group_members.add(message.channel)
                    elif message.channel in this_group_members:
                        this_group_members.remove(message.channel)

        elif isinstance(message, PushButtonStatusMessage):
            _channel_offset = self.calc_channel_offset(message.address)
            for channel in message.opened:
                if _channel_offset + channel > 64:  # ignore groups
                    continue
                await self._update_channel((_channel_offset + channel), {"state": 0})
            # ignore message.closed: we don't know at what dimlevel they're started

        elif isinstance(message, DimValueStatus):
            for offset, dim_value in enumerate(message.dim_values):
                channel = message.channel + offset
                if channel <= 64:  # channel
                    await self._update_channel(channel, {"state": dim_value})
                elif channel <= 80:  # group
                    group_num = channel - 65
                    for chan in self.group_members.get(group_num, []):
                        await self._update_channel(chan, {"state": dim_value})
                else:  # broadcast
                    for channel_obj in self._channels.values():
                        setattr(channel_obj, "state", dim_value)
                        await channel_obj.maybe_status_update()

        elif isinstance(
            message,
            (
                SetLedMessage,
                ClearLedMessage,
                FastBlinkingLedMessage,
                SlowBlinkingLedMessage,
            ),
        ):
            pass

        else:
            return await super().on_message(message)
        return None

    async def _request_single_channel_name(self, channel_num: int) -> None:
        msg_type = commandRegistry.get_command(
            CHANNEL_NAME_REQUEST_COMMAND_CODE, self.get_type()
        )
        if msg_type is None:
            return
        msg = msg_type(self._address)
        msg.priority = PRIORITY_LOW
        msg.channels = channel_num
        await self.send_message(msg)
