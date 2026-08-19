"""Climate domain channels (Temperature and ThermostatChannel)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import math
import operator
from typing import TYPE_CHECKING, Any, Final

from velbusaio.channels import Channel
from velbusaio.config import ConfigParameter
from velbusaio.const import DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS
from velbusaio.domains.input.channel import Button
from velbusaio.exceptions import VelbusConfigError
from velbusaio.message import Message
from velbusaio.messages.sensor_temp_request import (
    TEMP_AUTOSEND_DISABLED,
    TEMP_AUTOSEND_INTERVAL_MAX,
    TEMP_AUTOSEND_INTERVAL_MIN,
    TEMP_AUTOSEND_ON_CHANGE,
    SensorTempRequest,
)
from velbusaio.messages.set_temperature import SetTemperatureMessage
from velbusaio.messages.switch_to_comfort import SwitchToComfortMessage
from velbusaio.messages.switch_to_day import SwitchToDayMessage
from velbusaio.messages.switch_to_night import SwitchToNightMessage
from velbusaio.messages.switch_to_safe import SwitchToSafeMessage
from velbusaio.messages.temp_sensor_settings_part1 import TempSensorSettingsPart1
from velbusaio.messages.temp_sensor_settings_part2 import TempSensorSettingsPart2
from velbusaio.messages.temp_sensor_settings_part3 import TempSensorSettingsPart3
from velbusaio.messages.temp_sensor_settings_part4 import TempSensorSettingsPart4
from velbusaio.messages.temp_sensor_settings_request import TempSensorSettingsRequest
from velbusaio.messages.temp_sensor_status import TempSensorStatusMessage
from velbusaio.messages.temp_set_cooling import TempSetCoolingMessage
from velbusaio.messages.temp_set_heating import TempSetHeatingMessage

if TYPE_CHECKING:
    from velbusaio.module import Module

_PRESET_TO_MESSAGE: dict[str, type[Message]] = {
    "safe": SwitchToSafeMessage,
    "comfort": SwitchToComfortMessage,
    "day": SwitchToDayMessage,
    "night": SwitchToNightMessage,
}

_MODE_TO_MESSAGE: dict[str, type[Message]] = {
    "cool": TempSetCoolingMessage,
    "heat": TempSetHeatingMessage,
}

_THERMOSTAT_NAME_TO_ATTR: dict[str, str] = {
    "Heater": "heater",
    "Boost": "boost",
    "Boost heater/cooler": "boost",
    "Pump": "pump",
    "Cooler": "cooler",
    "Alarm 1": "alarm1",
    "Alarm 2": "alarm2",
    "Alarm 3": "alarm3",
    "Alarm 4": "alarm4",
    "Temperature alarm 1": "alarm1",
    "Temperature alarm 2": "alarm2",
    "Temperature alarm 3": "alarm3",
    "Temperature alarm 4": "alarm4",
}

_PART1_FIELDS: Final = (
    "current_set",
    "comfort_heating",
    "day_heating",
    "night_heating",
    "antifreeze_heating",
    "temp_difference",
    "hysteresis",
)
_PART2_FIELDS: Final = (
    "comfort_cooling",
    "day_cooling",
    "night_cooling",
    "safe_cooling",
    "default_sleep_timer",
    "autosend_interval",
)
_PART3_FIELDS: Final = (
    "alarm_low",
    "alarm_high",
    "cool_lower",
    "heat_upper",
    "calibration",
    "slave_or_zone",
    "calibration_gain",
)
_PART4_FIELDS: Final = (
    "min_switching_time",
    "pump_delayed_on",
    "pump_delayed_off",
    "alarm_2",
    "alarm_3",
    "heat_lower",
    "cool_upper",
)

_FIELD_PART: Final[dict[str, int]] = {
    **dict.fromkeys(_PART1_FIELDS, 1),
    **dict.fromkeys(_PART2_FIELDS, 2),
    **dict.fromkeys(_PART3_FIELDS, 3),
    **dict.fromkeys(_PART4_FIELDS, 4),
}

_CONFIG_NUMBER_SPECS: Final[tuple[tuple[str, str, float, float], ...]] = (
    ("temp_difference", "Boost difference", -10.0, 10.0),
    ("hysteresis", "Hysteresis", 0.0, 15.5),
    ("default_sleep_timer", "Default sleep (min)", 1.0, 65279.0),
    ("autosend_interval", "Autosend interval (s)", 0.0, 255.0),
)


def module_supports_temp_settings(module_data: dict[str, Any]) -> bool:
    """Return True when the module advertises temperature settings commands."""
    cmds = module_data.get("CommandToClass", {})
    return (
        cmds.get("E7") == "TempSensorSettingsRequest"
        and cmds.get("E8") == "TempSensorSettingsPart1"
        and "TemperatureChannel" in module_data
    )


def infer_temp_settings_layout(module_data: dict[str, Any]) -> str:
    """Infer classic vs GP settings layout from the module type."""
    explicit = module_data.get("TempSettingsLayout")
    if explicit in ("classic", "gp"):
        return explicit
    module_type = str(module_data.get("Type", "")).upper()
    if module_type in {"VMB1TS", "VMB1TC", "VMB1TCW"}:
        return "classic"
    return "gp"


class ThermostatChannel(Button):
    """A Thermostat output channel (heater/cooler/boost/pump/alarms)."""

    def __init__(
        self,
        module: Module,
        num: int,
        name: str,
        nameEditable: bool,
        subDevice: bool,
        address: int,
    ) -> None:
        super().__init__(module, num, name, nameEditable, subDevice, address)
        attr_name = _THERMOSTAT_NAME_TO_ATTR.get(self.name)
        self._extractor: Callable[[TempSensorStatusMessage], bool] | None = (
            operator.attrgetter(attr_name) if attr_name else None
        )

    def __setstate__(self, state: dict) -> None:
        super().__setstate__(state)
        attr_name = _THERMOSTAT_NAME_TO_ATTR.get(self.name)
        self._extractor = operator.attrgetter(attr_name) if attr_name else None

    async def update_status_from_message(
        self, message: TempSensorStatusMessage, sub_idx: int = 0
    ) -> None:
        """Update thermostat channel state from status message."""
        if self._extractor is not None:
            await self.set_closed(bool(self._extractor(message)))
        elif sub_idx:
            await self.set_closed(bool(sub_idx))


class Temperature(Channel):
    """A Temperature sensor and climate control channel."""

    cur: float = 0.0
    cur_precision: float | None = None
    max: float | None = None
    min: float | None = None
    target: float = 0.0
    cmode: str | None = None
    cool_mode: str | None = None
    cstatus: str | None = None
    thermostat: bool = False
    sleep_timer: int = 0

    current_set: float | None = None
    comfort_heating: float | None = None
    day_heating: float | None = None
    night_heating: float | None = None
    antifreeze_heating: float | None = None
    temp_difference: float | None = None
    hysteresis: float | None = None
    comfort_cooling: float | None = None
    day_cooling: float | None = None
    night_cooling: float | None = None
    safe_cooling: float | None = None
    default_sleep_timer: int | None = None
    autosend_interval: int | None = None
    alarm_low: float | None = None
    alarm_high: float | None = None
    cool_lower: float | None = None
    heat_upper: float | None = None
    calibration: float | None = None
    slave_or_zone: int | None = None
    calibration_gain: int | None = None
    min_switching_time: int | None = None
    pump_delayed_on: int | None = None
    pump_delayed_off: int | None = None
    alarm_2: float | None = None
    alarm_3: float | None = None
    heat_lower: float | None = None
    cool_upper: float | None = None

    def __init__(
        self,
        module: Module,
        num: int,
        name: str,
        nameEditable: bool,
        subDevice: bool,
        address: int,
    ) -> None:
        super().__init__(module, num, name, nameEditable, subDevice, address)
        self._settings: dict[str, Any] = {}

    def _get_module_data(self) -> dict[str, Any]:
        if self.module is None:
            return {}
        spec = getattr(self.module, "spec", None)
        if spec is not None and hasattr(spec, "type_name"):
            return {
                "Type": spec.type_name,
                "TemperatureChannel": spec.temperature_channel,
                "CommandToClass": {
                    k: v.__name__ if hasattr(v, "__name__") else str(v)
                    for k, v in spec.command_to_class.items()
                },
            }
        if isinstance(spec, dict):
            return spec
        return getattr(self.module, "_data", {}) or {}

    def supports_temp_settings(self) -> bool:
        return module_supports_temp_settings(self._get_module_data())

    def has_part2(self) -> bool:
        cmds = self._get_module_data().get("CommandToClass", {})
        return cmds.get("E9") == "TempSensorSettingsPart2"

    def has_part3(self) -> bool:
        cmds = self._get_module_data().get("CommandToClass", {})
        return cmds.get("C6") == "TempSensorSettingsPart3"

    def has_part4(self) -> bool:
        cmds = self._get_module_data().get("CommandToClass", {})
        return cmds.get("B9") == "TempSensorSettingsPart4"

    def get_settings_layout(self) -> str:
        return infer_temp_settings_layout(self._get_module_data())

    async def update_settings_part1(
        self,
        *,
        current_set: float,
        comfort_heating: float,
        day_heating: float,
        night_heating: float,
        antifreeze_heating: float,
        temp_difference: float,
        hysteresis: float,
    ) -> None:
        """Update Part1 temperature settings."""
        self._settings.update(
            {
                "current_set": current_set,
                "comfort_heating": comfort_heating,
                "day_heating": day_heating,
                "night_heating": night_heating,
                "antifreeze_heating": antifreeze_heating,
                "temp_difference": temp_difference,
                "hysteresis": hysteresis,
            }
        )
        self.current_set = current_set
        self.comfort_heating = comfort_heating
        self.day_heating = day_heating
        self.night_heating = night_heating
        self.antifreeze_heating = antifreeze_heating
        self.temp_difference = temp_difference
        self.hysteresis = hysteresis
        await self.maybe_status_update()

    async def update_settings_part2(
        self,
        *,
        comfort_cooling: float,
        day_cooling: float,
        night_cooling: float,
        safe_cooling: float,
        default_sleep_timer: int,
        autosend_interval: int,
    ) -> None:
        """Update Part2 temperature settings."""
        self._settings.update(
            {
                "comfort_cooling": comfort_cooling,
                "day_cooling": day_cooling,
                "night_cooling": night_cooling,
                "safe_cooling": safe_cooling,
                "default_sleep_timer": default_sleep_timer,
                "autosend_interval": autosend_interval,
            }
        )
        self.comfort_cooling = comfort_cooling
        self.day_cooling = day_cooling
        self.night_cooling = night_cooling
        self.safe_cooling = safe_cooling
        self.default_sleep_timer = default_sleep_timer
        self.autosend_interval = autosend_interval
        await self.maybe_status_update()

    async def update_settings_part3(
        self,
        *,
        alarm_low: float,
        alarm_high: float,
        cool_lower: float,
        heat_upper: float,
        calibration: float,
        slave_or_zone: int,
        calibration_gain: int,
    ) -> None:
        """Update Part3 temperature settings."""
        self._settings.update(
            {
                "alarm_low": alarm_low,
                "alarm_high": alarm_high,
                "cool_lower": cool_lower,
                "heat_upper": heat_upper,
                "calibration": calibration,
                "slave_or_zone": slave_or_zone,
                "calibration_gain": calibration_gain,
            }
        )
        self.alarm_low = alarm_low
        self.alarm_high = alarm_high
        self.cool_lower = cool_lower
        self.heat_upper = heat_upper
        self.calibration = calibration
        self.slave_or_zone = slave_or_zone
        self.calibration_gain = calibration_gain
        await self.maybe_status_update()

    async def update_settings_part4(
        self,
        *,
        min_switching_time: int,
        pump_delayed_on: int,
        pump_delayed_off: int,
        alarm_2: float,
        alarm_3: float,
        heat_lower: float,
        cool_upper: float,
    ) -> None:
        """Update Part4 temperature settings."""
        self._settings.update(
            {
                "min_switching_time": min_switching_time,
                "pump_delayed_on": pump_delayed_on,
                "pump_delayed_off": pump_delayed_off,
                "alarm_2": alarm_2,
                "alarm_3": alarm_3,
                "heat_lower": heat_lower,
                "cool_upper": cool_upper,
            }
        )
        self.min_switching_time = min_switching_time
        self.pump_delayed_on = pump_delayed_on
        self.pump_delayed_off = pump_delayed_off
        self.alarm_2 = alarm_2
        self.alarm_3 = alarm_3
        self.heat_lower = heat_lower
        self.cool_upper = cool_upper
        await self.maybe_status_update()

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get one cached setting value."""
        return self._settings.get(key, default)

    @property
    def settings(self) -> dict[str, Any]:
        """Return a copy of the settings dictionary."""
        return dict(self._settings)

    async def request_settings(self) -> None:
        """Request temperature sensor settings over the bus."""
        await self.send_message(TempSensorSettingsRequest(self._address))

    async def set_setting(self, key: str, value: Any) -> None:
        """Set a single temperature setting and write the corresponding Part frame."""
        if key not in _FIELD_PART:
            raise VelbusConfigError(f"Unknown temperature setting: {key!r}")
        part = _FIELD_PART[key]
        if part == 2 and not self.has_part2():
            raise VelbusConfigError(f"{key} requires settings Part2")
        if part == 3 and not self.has_part3():
            raise VelbusConfigError(f"{key} requires settings Part3")
        if part == 4 and not self.has_part4():
            raise VelbusConfigError(f"{key} requires settings Part4")
        if key in (
            "default_sleep_timer",
            "autosend_interval",
            "slave_or_zone",
            "calibration_gain",
            "min_switching_time",
            "pump_delayed_on",
            "pump_delayed_off",
        ):
            value = int(value)
        else:
            value = float(value)
        self._settings[key] = value
        setattr(self, key, value)
        await self._write_settings_part(part)
        await self.maybe_status_update()

    async def _write_settings_part(self, part: int) -> None:
        if part == 1:
            msg = TempSensorSettingsPart1(self.address)
            for name in _PART1_FIELDS:
                setattr(msg, name, self._settings.get(name, 0))
        elif part == 2:
            msg = TempSensorSettingsPart2(self.address)
            for name in _PART2_FIELDS:
                setattr(msg, name, self._settings.get(name, 0))
        elif part == 3:
            msg = TempSensorSettingsPart3(
                self.address, layout=self.get_settings_layout()
            )
            for name in _PART3_FIELDS:
                setattr(
                    msg,
                    name,
                    self._settings.get(name, 0 if name != "slave_or_zone" else 0xFF),
                )
        elif part == 4:
            msg = TempSensorSettingsPart4(
                self.address, layout=self.get_settings_layout()
            )
            for name in _PART4_FIELDS:
                setattr(msg, name, self._settings.get(name, 0))
        else:
            raise VelbusConfigError(f"Unknown settings part: {part}")
        await self.send_message(msg)

    def get_config_parameters(self) -> list[ConfigParameter]:
        """Return discoverable CONFIG parameters for this thermostat."""
        params: list[ConfigParameter] = []
        for key, label, min_value, max_value in _CONFIG_NUMBER_SPECS:
            part = _FIELD_PART[key]
            if part == 2 and not self.has_part2():
                continue
            params.append(
                ConfigParameter(
                    key=key,
                    label=label,
                    kind="number",
                    getter=self._make_config_getter(key),
                    setter=self._make_config_setter(key),
                    min_value=min_value,
                    max_value=max_value,
                    channel=self.channel_number,
                    metadata={
                        "unit": (
                            "min"
                            if key == "default_sleep_timer"
                            else "s"
                            if key == "autosend_interval"
                            else "°C"
                        )
                    },
                )
            )
        return params

    def _make_config_getter(self, key: str) -> Callable[[], Awaitable[Any]]:
        async def getter() -> Any:
            return self._settings.get(key)

        return getter

    def _make_config_setter(self, key: str) -> Callable[[Any], Awaitable[None]]:
        async def setter(value: Any) -> None:
            await self.set_setting(key, value)

        return setter

    async def update_sensor_temperature(
        self, cur: float, min_temp: float | None = None, max_temp: float | None = None
    ) -> None:
        """Update temperature sensor readings."""
        self.cur = cur
        if min_temp is not None:
            self.min = min_temp
        if max_temp is not None:
            self.max = max_temp
        await self.maybe_status_update()

    async def update_thermostat_status(
        self,
        *,
        target_temp: float,
        mode: int,
        status_mode: int,
        sleep_timer: int,
        cool_mode: str,
        current_temp: float,
    ) -> None:
        """Update thermostat operation status."""
        status_map = {0: "run", 1: "manual", 2: "sleep", 3: "disable"}
        mode_map = {0: "safe", 1: "night", 2: "day", 4: "comfort"}
        self.target = target_temp
        self.cmode = mode_map.get(mode, "safe")
        self.cstatus = status_map.get(status_mode, "run")
        self.sleep_timer = sleep_timer
        self.cool_mode = cool_mode
        await self.maybe_update_temperature(current_temp, 1 / 2)
        await self.maybe_status_update()

    def get_categories(self) -> list[str]:
        """Return the categories for this channel."""
        if self.thermostat:
            return ["sensor", "climate"]
        return ["sensor"]

    def get_unit(self) -> str:
        """Return the unit of measurement for this channel."""
        return TEMP_CELSIUS

    def get_state(self) -> float:
        """Return the current state of the temperature sensor."""
        return round(float(self.cur), 2)

    def get_sensor_type(self) -> str:
        """Return the sensor type."""
        return "temperature"

    def get_max(self) -> int | None:
        """Return the maximum temperature recorded."""
        if self.max is None:
            return None
        return round(self.max, 2)

    def get_min(self) -> int | None:
        """Return the minimum temperature recorded."""
        if self.min is None:
            return None
        return round(self.min, 2)

    def get_climate_target(self) -> int:
        """Return the target temperature."""
        return round(self.target, 2)

    def get_climate_preset(self) -> str | None:
        """Return the climate preset."""
        return self.cmode

    def get_climate_mode(self) -> str | None:
        """Return the climate mode."""
        return self.cstatus

    def get_cool_mode(self) -> str | None:
        """Return the cool mode."""
        return self.cool_mode

    async def set_temp(self, temp: float) -> None:
        """Set the target temperature."""
        msg = self.create_message(SetTemperatureMessage)
        msg.temp = temp
        await self.send_message(msg)

    async def set_temperature_autosend(
        self, mode: str, seconds: int | None = None
    ) -> None:
        """Configure how often the module sends its temperature on the bus.

        :param mode: one of ``"never"`` (auto send disabled),
            ``"on_change"`` (auto send on every temperature change) or
            ``"interval"`` (a fixed interval, requires ``seconds``).
        :param seconds: the interval in seconds (10..255), only used and
            required when ``mode`` is ``"interval"``.
        """
        if mode == "never":
            interval = TEMP_AUTOSEND_DISABLED
        elif mode == "on_change":
            interval = TEMP_AUTOSEND_ON_CHANGE
        elif mode == "interval":
            if seconds is None:
                raise ValueError("seconds is required when mode is 'interval'")
            if not TEMP_AUTOSEND_INTERVAL_MIN <= seconds <= TEMP_AUTOSEND_INTERVAL_MAX:
                raise ValueError(
                    "seconds must be between "
                    f"{TEMP_AUTOSEND_INTERVAL_MIN} and {TEMP_AUTOSEND_INTERVAL_MAX}"
                )
            interval = seconds
        else:
            raise ValueError(
                f"Unknown temperature autosend mode: {mode!r} "
                "(expected 'never', 'on_change' or 'interval')"
            )
        msg = self.create_message(SensorTempRequest)
        msg.autosend_interval = interval
        await self.send_message(msg)

    async def _switch_mode(self) -> None:
        """Switch the climate mode."""
        msg_cls = _PRESET_TO_MESSAGE.get(self.cmode, SwitchToNightMessage)

        if self.cstatus == "run":
            sleep = 0x0
        elif self.cstatus == "manual":
            sleep = 0xFFFF
        elif self.cstatus == "sleep":
            sleep = self.sleep_timer or 0
        else:
            sleep = 0x0
        msg = self.create_message(msg_cls)
        msg.sleep = sleep
        await self.send_message(msg)

    async def set_preset(self, preset: str) -> None:
        """Set the climate preset."""
        self.cmode = preset
        await self._switch_mode()

    async def set_climate_mode(self, mode: str) -> None:
        """Set the climate mode."""
        self.cstatus = mode
        await self._switch_mode()

    async def set_mode(self, mode: str) -> None:
        """Set the heat/cool mode."""
        msg_cls = _MODE_TO_MESSAGE.get(mode, TempSetHeatingMessage)
        msg = self.create_message(msg_cls)
        await self.send_message(msg)

    async def maybe_update_temperature(self, new_temp: float, precision: float) -> None:
        """Update the temperature only if the new value is different enough."""
        current_temp_rounded_to_precision = math.floor(self.cur / precision) * precision

        if current_temp_rounded_to_precision == new_temp:
            return

        if (
            current_temp_rounded_to_precision - precision
            <= new_temp
            < current_temp_rounded_to_precision
            and self.cur_precision is not None
            and self.cur_precision < precision
        ):
            new_temp = current_temp_rounded_to_precision - self.cur_precision

        self.cur = new_temp
        self.cur_precision = precision
        await self.maybe_status_update()
