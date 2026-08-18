"""Field descriptors for declarative Velbus message definitions.

This module provides a declarative way to define message structures,
eliminating boilerplate in populate() and data_to_binary() methods.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json
from typing import Any, ClassVar, TypeVar, overload

from velbusaio.command_registry import CommandRegistryError, commandRegistry
from velbusaio.const import MessagePriority
from velbusaio.message import Message

T = TypeVar("T")


class Field[T]:
    """Base field descriptor for message attributes."""

    serializable: bool = True

    def __init__(
        self,
        byte_index: int | None = None,
        default: T | None = None,
        parser: Callable[[bytes], T] | None = None,
        serializer: Callable[[T], bytes] | None = None,
        *,
        serializable: bool | None = None,
        json_map: Mapping[Any, Any] | Callable[[Any], Any] | None = None,
        json_name: str | None = None,
    ) -> None:
        """Initialize field descriptor."""
        self.byte_index = byte_index
        self.default = default
        self.parser = parser
        self.serializer = serializer
        self.json_map = json_map
        self.json_name = json_name
        if serializable is not None:
            self.serializable = serializable
        self.name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        """Store the field name."""
        self.name = name

    @overload
    def __get__(self, obj: None, objtype: type | None = None) -> Field[T]: ...

    @overload
    def __get__(self, obj: Any, objtype: type | None = None) -> T: ...

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        """Get the field value."""
        if obj is None:
            return self
        if self.name is None:
            raise AttributeError("Field name is not set")
        return obj.__dict__.get(self.name, self.default)

    def __set__(self, obj: Any, value: T) -> None:
        """Set the field value."""
        if self.name is None:
            raise AttributeError("Field name is not set")
        obj.__dict__[self.name] = value

    def parse(self, data: bytes) -> Any:
        """Parse value from data bytes."""
        if self.parser is not None:
            return self.parser(data)
        if self.byte_index is not None:
            return data[self.byte_index]
        return self.default

    def serialize(self, value: Any) -> bytes:
        """Serialize value to bytes."""
        if self.serializer is not None:
            return self.serializer(value)
        if isinstance(value, int):
            return bytes([value])
        return b""

    def to_json_value(self, value: Any) -> Any:
        """Convert a parsed value for JSON output."""
        if callable(self.json_map):
            return self.json_map(value)
        if self.json_map is not None:
            if isinstance(value, (list, tuple)):
                return [self.json_map.get(v, v) for v in value]
            return self.json_map.get(value, value)
        return value


class ByteField(Field[int]):
    """Single byte field."""

    def __init__(self, byte_index: int, default: int | None = 0, **kwargs: Any) -> None:
        """Initialize byte field."""
        if byte_index < 0:
            raise ValueError(f"byte_index must be >= 0, got {byte_index}")
        super().__init__(byte_index=byte_index, default=default, **kwargs)


    def parse(self, data: bytes) -> Any:
        """Parse byte from data."""
        assert self.byte_index is not None
        if self.byte_index >= len(data):
            return self.default
        return data[self.byte_index]


    def serialize(self, value: int) -> bytes:
        """Serialize to single byte."""
        return bytes([value])


class BitField(Field[Any]):
    """Bit or bit-range field within a single byte."""

    def __init__(
        self,
        byte_index: int,
        *,
        bit: int | None = None,
        bit_range: tuple[int, int] | None = None,
        bit_start: int | None = None,
        bit_count: int = 1,
        offset: int = 0,
        default: Any = 0,
        as_bool: bool | None = None,
        json_map: dict[Any, Any] | None = None,
        serializable: bool = True,
    ) -> None:
        """Initialize bit field."""
        if byte_index < 0:
            raise ValueError(f"byte_index must be >= 0, got {byte_index}")

        specified = sum(x is not None for x in (bit, bit_range, bit_start))
        if specified != 1:
            raise ValueError(
                "Must specify exactly one of: bit, bit_range, or bit_start"
            )

        if bit is not None:
            if not (0 <= bit <= 7):
                raise ValueError(f"bit must be between 0 and 7, got {bit}")
            mask = 1 << bit
            shift = bit
            if as_bool is None:
                as_bool = True

        elif bit_range is not None:
            start, end = bit_range
            if not (0 <= start <= end <= 7):
                raise ValueError(
                    f"bit_range must satisfy 0 <= start <= end <= 7, got {bit_range}"
                )
            count = end - start + 1
            mask = ((1 << count) - 1) << start
            shift = start
            if as_bool is None:
                as_bool = False

        else:  # bit_start is not None
            assert bit_start is not None
            if not (0 <= bit_start <= 7):
                raise ValueError(f"bit_start must be between 0 and 7, got {bit_start}")
            if not (1 <= bit_count <= 8 - bit_start):
                raise ValueError(
                    f"bit_count must be between 1 and {8 - bit_start} for bit_start={bit_start}, got {bit_count}"
                )
            mask = ((1 << bit_count) - 1) << bit_start
            shift = bit_start
            if as_bool is None:
                as_bool = False

        super().__init__(
            byte_index=byte_index,
            default=default,
            json_map=json_map,
            serializable=serializable,
        )

        self.mask = mask
        self.shift = shift
        self.offset = offset
        self.as_bool = bool(as_bool)

    def parse(self, data: bytes) -> Any:
        """Parse masked bits from data."""
        assert self.byte_index is not None
        value = data[self.byte_index] & self.mask
        if self.shift:
            value >>= self.shift
        if self.as_bool:
            return value != 0
        return value + self.offset

    def serialize(self, value: Any) -> bytes:
        """Serialize bit field (rarely used on transmit messages)."""
        if self.as_bool:
            bit_value = self.mask if value else 0
        else:
            bit_value = ((int(value) - self.offset) << self.shift) & self.mask
        return bytes([bit_value])


class MappedField(Field[Any]):
    """Field whose JSON representation uses a lookup map."""

    def __init__(
        self,
        byte_index: int | None = None,
        *,
        default: Any = None,
        parser: Callable[[bytes], Any] | None = None,
        serializer: Callable[[Any], bytes] | None = None,
        json_map: dict[Any, Any] | None = None,
        serializable: bool = True,
    ) -> None:
        """Initialize mapped field."""
        super().__init__(
            byte_index=byte_index,
            default=default,
            parser=parser,
            serializer=serializer,
            json_map=json_map,
            serializable=serializable,
        )


class ComputedField(Field[Any]):
    """Derived field populated from data but not tied to a fixed byte index."""

    def __init__(
        self,
        parser: Callable[[bytes], Any],
        *,
        default: Any = None,
        serializer: Callable[[Any], bytes] | None = None,
        serializable: bool = False,
        json_map: dict[Any, Any] | None = None,
    ) -> None:
        """Initialize computed field."""
        super().__init__(
            byte_index=None,
            default=default,
            parser=parser,
            serializer=serializer,
            serializable=serializable,
            json_map=json_map,
        )


class RawTailField(Field[bytes]):
    """Remaining bytes from a start index."""

    def __init__(self, start_index: int, default: bytes = b"") -> None:
        """Initialize raw tail field."""
        super().__init__(
            byte_index=start_index,
            default=default,
            parser=lambda data, start=start_index: data[start:],
            serializer=bytes,
        )
        self.start_index = start_index

    def parse(self, data: bytes) -> bytes:
        """Parse remaining bytes."""
        return data[self.start_index :]


class ChannelsField(Field[list[int]]):
    """Field for channel bitmask parsing."""

    def __init__(
        self, byte_index: int, default: list[int] | None = None, **kwargs: Any
    ) -> None:
        """Initialize channels field."""
        super().__init__(byte_index=byte_index, default=default or [], **kwargs)

    def parse(self, data: bytes) -> list[int]:
        """Parse channels from bitmask byte."""
        assert self.byte_index is not None
        byte_value = data[self.byte_index]
        return [offset + 1 for offset in range(8) if byte_value & (1 << offset)]

    def serialize(self, channels: Any) -> bytes:
        """Serialize channels to bitmask byte."""
        if isinstance(channels, str):
            try:
                return bytes([int(channels, 16)])
            except ValueError:
                return bytes([0xFF])
        if not isinstance(channels, (list, tuple, set)):
            return bytes([int(channels)])
        result = 0
        for offset in range(8):
            if offset + 1 in channels:
                result += 1 << offset
        return bytes([result])


class ChannelField(Field[int]):
    """Field for single channel parsing from a bitmask byte."""

    def __init__(self, byte_index: int, default: int = 0, **kwargs: Any) -> None:
        """Initialize channel field."""
        super().__init__(byte_index=byte_index, default=default, **kwargs)

    def parse(self, data: bytes) -> int:
        """Parse single channel from bitmask byte."""
        assert self.byte_index is not None
        byte_value = data[self.byte_index]
        channels = [offset + 1 for offset in range(8) if byte_value & (1 << offset)]
        if len(channels) != 1:
            raise ValueError(f"Expected exactly one channel, got {len(channels)}")
        return channels[0]

    def serialize(self, channel: int) -> bytes:
        """Serialize single channel to bitmask byte."""
        if channel <= 0:
            return bytes([0x00])
        return bytes([1 << (channel - 1)])


class ChannelIndexField(Field[list[int]]):
    """Channel index byte (1-8), stored as list[int] for API consistency."""

    def __init__(
        self, byte_index: int, default: list[int] | None = None, **kwargs: Any
    ) -> None:
        """Initialize channel index field."""
        super().__init__(byte_index=byte_index, default=default or [], **kwargs)

    def parse(self, data: bytes) -> list[int]:
        """Parse channel index byte to list of one channel (or empty)."""
        assert self.byte_index is not None
        value = data[self.byte_index]
        return [value] if value else []

    def serialize(self, channels: list[int]) -> bytes:
        """Serialize first channel to index byte (1-8), or 0 if empty."""
        return bytes([channels[0] if channels else 0])


class Int16Field(Field[int]):
    """16-bit integer field (big-endian)."""

    def __init__(
        self,
        byte_index: int,
        default: int | None = 0,
        *,
        signed: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize 16-bit field."""
        super().__init__(byte_index=byte_index, default=default, **kwargs)
        self.signed = signed

    def parse(self, data: bytes) -> int:
        """Parse 16-bit value from two bytes."""
        assert self.byte_index is not None
        if self.byte_index + 1 >= len(data):
            return self.default or 0
        value = (data[self.byte_index] << 8) | data[self.byte_index + 1]
        if self.signed and value & 0x8000:
            value -= 0x10000
        return value

    def serialize(self, value: int) -> bytes:
        """Serialize to two bytes (big-endian)."""
        if value < 0:
            value += 0x10000
        return bytes([value >> 8, value & 0xFF])


class Int24Field(Field[int]):
    """24-bit integer field (big-endian, 3 bytes)."""

    def __init__(
        self,
        byte_index: int,
        default: int = 0,
        *,
        bit_range: tuple[int, int] | None = None,
        mask: int | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize 24-bit field."""
        super().__init__(byte_index=byte_index, default=default, **kwargs)
        if bit_range is not None:
            start, end = bit_range
            count = end - start + 1
            self.mask = ((1 << count) - 1) << start
            self.shift = start
        else:
            self.mask = mask
            self.shift = 0

    def parse(self, data: bytes) -> int:
        """Parse 24-bit value from three bytes."""
        assert self.byte_index is not None
        val = (
            (data[self.byte_index] << 16)
            | (data[self.byte_index + 1] << 8)
            | data[self.byte_index + 2]
        )
        if self.mask is not None:
            val &= self.mask
        if self.shift:
            val >>= self.shift
        return val

    def serialize(self, value: int) -> bytes:
        """Serialize to three bytes (big-endian)."""
        val = int(value)
        if self.shift:
            val <<= self.shift
        if self.mask is not None:
            val &= self.mask
        return bytes([(val >> 16) & 0xFF, (val >> 8) & 0xFF, val & 0xFF])




class Int32Field(Field[int]):
    """32-bit integer field (big-endian, 4 bytes)."""

    def __init__(self, byte_index: int, default: int = 0, **kwargs: Any) -> None:
        """Initialize 32-bit field."""
        super().__init__(byte_index=byte_index, default=default, **kwargs)

    def parse(self, data: bytes) -> int:
        """Parse 32-bit value from four bytes."""
        assert self.byte_index is not None
        return (
            (data[self.byte_index] << 24)
            | (data[self.byte_index + 1] << 16)
            | (data[self.byte_index + 2] << 8)
            | data[self.byte_index + 3]
        )

    def serialize(self, value: int) -> bytes:
        """Serialize to four bytes (big-endian)."""
        return bytes(
            [
                (value >> 24) & 0xFF,
                (value >> 16) & 0xFF,
                (value >> 8) & 0xFF,
                value & 0xFF,
            ]
        )


class BlindChannelField(Field[int]):
    """Channel field for VMB1BL/VMB2BL blind modules.

    Note on encoding asymmetry:
    - Incoming status frames: VMB1BL/VMB2BL modules report individual relay status
      bits (e.g. bit 1 = 0x02 for Channel 1 Output 1). parse() extracts the channel (1 or 2).
    - Outgoing command frames: Velbus requires sending the combined relay bitmask for
      all outputs of that channel (0x03 = 0x01|0x02 for Channel 1 outputs 1&2; 0x0C = 0x04|0x08 for Channel 2 outputs 3&4).
      serialize() produces this combined command bitmask.
    """

    def __init__(self, byte_index: int, default: int = 0, **kwargs: Any) -> None:
        """Initialize blind channel field."""
        super().__init__(byte_index=byte_index, default=default, **kwargs)

    def parse(self, data: bytes) -> int:
        """Parse channel (1 or 2) from VMB1BL/VMB2BL incoming status byte."""
        assert self.byte_index is not None
        tmp = (data[self.byte_index] >> 1) & 0x03
        return 1 if tmp == 1 else 2

    def serialize(self, channel: int) -> bytes:
        """Serialize channel to VMB1BL/VMB2BL outgoing command relay bitmask (0x03 for ch1, 0x0C for ch2)."""
        return bytes([0x03 if channel == 1 else 0x0C])



class BlindStatusField(Field[int]):
    """Status field for VMB1BL/VMB2BL blind status."""

    def __init__(
        self,
        byte_index: int,
        channel_byte_index: int = 0,
        default: int = 0,
        **kwargs: Any,
    ) -> None:
        """Initialize blind status field."""
        super().__init__(
            byte_index=byte_index, default=default, serializable=False, **kwargs
        )
        self.channel_byte_index = channel_byte_index

    def parse(self, data: bytes) -> int:
        """Parse 2-bit status for this channel from status byte."""
        assert self.byte_index is not None
        tmp = (data[self.channel_byte_index] >> 1) & 0x03
        channel = 1 if tmp == 1 else 2
        return (data[self.byte_index] >> ((channel - 1) * 2)) & 0x03

    def serialize(self, value: int) -> bytes:
        """Serialize placeholder for receive-only messages."""
        return bytes([value])


class TemperatureField(Field[float]):
    """Temperature field with special Velbus encoding."""

    def __init__(self, byte_index: int, default: float = 0.0, **kwargs: Any) -> None:
        """Initialize temperature field."""
        super().__init__(byte_index=byte_index, default=default, **kwargs)

    def parse(self, data: bytes) -> float:
        """Parse temperature from two bytes."""
        assert self.byte_index is not None
        raw = (data[self.byte_index] << 8) | data[self.byte_index + 1]
        if raw >> 15:
            return -127 + (raw / 32 * 0.0625)
        return (raw / 32) * 0.0625

    def serialize(self, value: float) -> bytes:
        """Serialize temperature to two bytes."""
        if value < 0:
            raw = int((value + 127) / 0.0625 * 32) | 0x8000
        else:
            raw = int(value / 0.0625 * 32)
        return bytes([raw >> 8, raw & 0xFF])


class HalfDegreeField(Field[float]):
    """One-byte temperature with 0.5°C resolution (two's complement when signed)."""

    def __init__(
        self,
        byte_index: int,
        default: float = 0.0,
        *,
        signed: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize half-degree temperature field."""
        super().__init__(byte_index=byte_index, default=default, **kwargs)
        self.signed = signed

    def parse(self, data: bytes) -> float:
        """Parse a half-degree temperature byte."""
        assert self.byte_index is not None
        if self.byte_index >= len(data):
            return self.default
        raw = data[self.byte_index]
        if self.signed and raw & 0x80:
            raw -= 0x100
        return raw / 2

    def serialize(self, value: float) -> bytes:
        """Serialize a half-degree temperature byte."""
        return bytes([int(round(value * 2)) & 0xFF])


class StringField(Field[str]):
    """String field for text data."""

    def __init__(
        self,
        start_index: int,
        length: int | None = None,
        default: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize string field."""
        super().__init__(byte_index=start_index, default=default, **kwargs)
        self.length = length

    def parse(self, data: bytes) -> str:
        """Parse string from bytes."""
        assert self.byte_index is not None
        if self.length is not None:
            end_index = self.byte_index + self.length
            string_bytes = data[self.byte_index : end_index]
        else:
            string_bytes = data[self.byte_index :]
        return "".join(chr(x) for x in string_bytes if x != 0)

    def serialize(self, value: str) -> bytes:
        """Serialize string to bytes."""
        encoded = value.encode("ascii", "ignore")
        if self.length is None:
            return encoded
        padded = encoded[: self.length]
        return padded + bytes(self.length - len(padded))


def _collect_fields(cls: type) -> dict[str, Field]:
    """Collect Field descriptors from the class MRO."""
    fields: dict[str, Field] = {}
    for base in reversed(cls.__mro__):
        if base is object:
            continue
        fields.update(
            {
                name: value
                for name, value in base.__dict__.items()
                if isinstance(value, Field)
            }
        )
    return fields


def _validate_no_overlapping_bitfields(
    cls: type, fields: dict[str, Field]
) -> None:
    """Validate that no BitFields on the same byte share bit masks."""
    used_masks: dict[int, int] = {}
    field_names_by_bit: dict[tuple[int, int], str] = {}

    for name, field in fields.items():
        if isinstance(field, BitField) and field.byte_index is not None:
            byte_idx = field.byte_index
            mask = field.mask
            occupied = used_masks.get(byte_idx, 0)
            if occupied & mask:
                overlapping_mask = occupied & mask
                existing_field = next(
                    f_name
                    for (b, b_mask), f_name in field_names_by_bit.items()
                    if b == byte_idx and (b_mask & overlapping_mask)
                )
                raise TypeError(
                    f"Overlapping bitfields on byte {byte_idx} in {cls.__name__}: "
                    f"field '{name}' (mask 0x{mask:02X}) overlaps with '{existing_field}'"
                )
            used_masks[byte_idx] = occupied | mask
            field_names_by_bit[(byte_idx, mask)] = name



def _validate_data(
    self: DeclarativeMessage,
    priority: MessagePriority,
    rtr: bool,
    data: bytes,
) -> None:
    """Run standard payload validations."""
    priority_setting = self._priority
    if priority_setting is not None and priority != priority_setting:
        if priority_setting == MessagePriority.LOW:
            self.parser_error("needs low priority set")
        elif priority_setting == MessagePriority.HIGH:
            self.parser_error("needs high priority set")
        elif priority_setting == MessagePriority.FIRMWARE:
            self.parser_error("needs firmware priority set")
        else:
            self.parser_error(f"needs {priority_setting.name.lower()} priority set")

    if self._rtr and not rtr:
        self.parser_error("needs rtr set")
    elif not self._rtr and rtr:
        self.parser_error("does not need rtr set")

    data_length = self._data_length
    if data_length is not None:
        if data_length == 0 and len(data) != 0:
            self.parser_error("has data included")
        elif data_length != 0 and len(data) < data_length:
            self.parser_error(f"needs {data_length} bytes of data have {len(data)}")


def _make_from_bytes(cls: type, fields: dict[str, Field]) -> Any:
    """Build from_bytes() classmethod for declarative messages."""

    @classmethod
    def from_bytes(
        cls: type[DeclarativeMessage],
        data: bytes | bytearray,
        address: int = 0,
        priority: MessagePriority = MessagePriority.LOW,
        rtr: bool = False,
    ) -> DeclarativeMessage:
        data_bytes = bytes(data)
        msg = cls(address=address)
        _validate_data(msg, priority, rtr, data_bytes)
        msg.priority = priority
        msg.rtr = rtr
        for field_name, field in fields.items():
            setattr(msg, field_name, field.parse(data_bytes))
        post_populate = getattr(msg, "_post_populate", None)
        if post_populate is not None:
            post_populate(data_bytes)
        return msg

    return from_bytes


def _serializable_fields(fields: dict[str, Field]) -> list[tuple[str, Field]]:
    """Return fields included in data_to_binary in declaration order."""
    return [(name, field) for name, field in fields.items() if field.serializable]


def _make_data_to_binary_no_fields(
    cls: type[DeclarativeMessage],
) -> Callable[[Any], bytes]:
    """Build data_to_binary() for messages with no serializable fields."""

    def data_to_binary(self: DeclarativeMessage) -> bytes:
        if self._rtr:
            return b""
        return bytes([cls._command_code])

    return data_to_binary


def _make_data_to_binary(
    cls: type[DeclarativeMessage], fields: dict[str, Field]
) -> Callable[[Any], bytes]:
    """Build data_to_binary() from serializable fields."""

    serializable = _serializable_fields(fields)

    def data_to_binary(self: DeclarativeMessage) -> bytes:
        byte_map: dict[int, int] = {}
        ordered_keys: list[int | str] = []

        for field_name, field in serializable:
            value = getattr(self, field_name, field.default)
            ser_bytes = field.serialize(value)

            if field.byte_index is not None and len(ser_bytes) == 1:
                idx = field.byte_index
                if idx not in byte_map:
                    byte_map[idx] = 0
                    ordered_keys.append(idx)
                byte_map[idx] |= ser_bytes[0]
            else:
                ordered_keys.append(field_name)

        payload = bytearray([cls._command_code])
        for key in ordered_keys:
            if isinstance(key, int):
                payload.append(byte_map[key])
            else:
                f_name: str = key  # type: ignore[assignment]
                f_field = fields[f_name]
                f_val = getattr(self, f_name, f_field.default)
                payload.extend(f_field.serialize(f_val))

        return bytes(payload)

    return data_to_binary



def _make_to_json_basic(
    cls: type, fields: dict[str, Field]
) -> Callable[[Any], dict[str, Any]]:
    """Build to_json_basic() including declared fields."""

    def to_json_basic(self: DeclarativeMessage) -> dict[str, Any]:
        payload = Message.to_json_basic(self)
        for field_name, field in fields.items():
            key = field.json_name if field.json_name is not None else field_name
            value = getattr(self, field_name, field.default)
            payload[key] = field.to_json_value(value)
        return payload

    return to_json_basic


def _make_to_json(cls: type, fields: dict[str, Field]) -> Callable[[Any], str]:
    """Build to_json() from to_json_basic()."""

    def to_json(self: DeclarativeMessage) -> str:
        return json.dumps(self.to_json_basic())

    return to_json


class DeclarativeMessage(Message):
    """Base class for declaratively defined Velbus messages."""

    _command_code: ClassVar[int]
    _module_types: ClassVar[list[str] | None] = None
    _priority: ClassVar[MessagePriority | None] = MessagePriority.LOW
    _rtr: ClassVar[bool] = False
    _data_length: ClassVar[int | None] = None
    _auto_register: ClassVar[bool] = False
    _generates_data_to_binary: ClassVar[bool] = True
    _generates_to_json: ClassVar[bool] = True

    _declarative_fields: ClassVar[dict[str, Field]] = {}

    def __init__(self, address: int = 0, *args: Any, **kwargs: Any) -> None:
        """Initialize message, priority, rtr, and declarative field defaults."""
        p = self._priority if self._priority is not None else MessagePriority.LOW
        super().__init__(address=address, priority=p, rtr=self._rtr)
        field_names = list(self._declarative_fields.keys())
        for index, arg in enumerate(args):
            if index < len(field_names):
                setattr(self, field_names[index], arg)
        for field_name, field in self._declarative_fields.items():
            if field_name in kwargs:
                setattr(self, field_name, kwargs[field_name])
            elif field_name not in self.__dict__:
                setattr(self, field_name, field.default)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Configure generated methods and optional registry hooks."""
        super().__init_subclass__(**kwargs)

        fields = _collect_fields(cls)
        _validate_no_overlapping_bitfields(cls, fields)
        cls._declarative_fields = fields


        if cls._auto_register and hasattr(cls, "_command_code"):
            module_types = cls._module_types
            if not module_types:
                raise CommandRegistryError(
                    f"{cls.__name__} has _auto_register enabled but no _module_types"
                )
            for module_type in module_types:
                commandRegistry.register_command(cls._command_code, cls, module_type)

        if "from_bytes" not in cls.__dict__:
            cls.from_bytes = _make_from_bytes(cls, fields)  # type: ignore[method-assign]

        if "data_to_binary" not in cls.__dict__ and cls._generates_data_to_binary:
            if cls._rtr:
                cls.data_to_binary = _make_data_to_binary_no_fields(cls)  # type: ignore[method-assign, assignment]
            elif hasattr(cls, "_command_code"):
                if _serializable_fields(fields):
                    cls.data_to_binary = _make_data_to_binary(cls, fields)  # type: ignore[method-assign, assignment]
                else:
                    cls.data_to_binary = _make_data_to_binary_no_fields(cls)  # type: ignore[method-assign, assignment]

        if cls._generates_to_json:
            if "to_json_basic" not in cls.__dict__:
                cls.to_json_basic = _make_to_json_basic(cls, fields)  # type: ignore[method-assign, assignment]
            if "to_json" not in cls.__dict__:
                cls.to_json = _make_to_json(cls, fields)  # type: ignore[method-assign, assignment]
