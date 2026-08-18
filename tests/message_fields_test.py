"""Unit tests for the declarative message field framework."""

from __future__ import annotations

import json

import pytest

from velbusaio.const import PRIORITY_HIGH, PRIORITY_LOW
from velbusaio.message import Message, ParserError
from velbusaio.message_fields import (
    BitField,
    ByteField,
    ChannelField,
    ChannelsField,
    ComputedField,
    DeclarativeMessage,
    Field,
    Int16Field,
    Int24Field,
    RawTailField,
    StringField,
)


class _LedExampleMessage(DeclarativeMessage):
    """Throwaway message mirroring SetLedMessage."""

    _command_code = 0xF6
    _data_length = 1

    leds = ChannelsField(0)


class _RelayStatusExampleMessage(DeclarativeMessage):
    """Throwaway message mirroring RelayStatusMessage layout."""

    _command_code = 0xFB
    _data_length = 7

    channel = ChannelField(0)
    disable_inhibit_forced = ByteField(1)
    status = ByteField(2)
    led_status = ByteField(3)
    delay_time = Int24Field(4)


class TestByteField:
    """Tests for ByteField."""

    def test_round_trip(self):
        """Test parse and serialize."""
        field = ByteField(1, default=0)
        data = bytes([0x00, 0xAB, 0x00])
        assert field.parse(data) == 0xAB
        assert field.serialize(0xAB) == bytes([0xAB])


class TestBitField:
    """Tests for BitField."""

    def test_bool_and_mask(self):
        """Test boolean and masked values."""
        cool_mode = BitField(0, bit=7)
        status_mode = BitField(0, bit_range=(1, 2))
        data = bytes([0x86, 0x00, 0x01])
        assert cool_mode.parse(data) is True
        assert status_mode.parse(data) == 3


class TestChannelField:
    """Tests for ChannelField."""

    def test_round_trip(self):
        """Test channel bitmask round trip."""
        field = ChannelField(0)
        assert field.parse(bytes([0x04])) == 3
        assert field.serialize(3) == bytes([0x04])

    def test_serialize_zero(self):
        """Test zero channel serializes to 0x00."""
        field = ChannelField(0)
        assert field.serialize(0) == bytes([0x00])


class TestIntFields:
    """Tests for multi-byte integer fields."""

    def test_int16_round_trip(self):
        """Test Int16Field."""
        field = Int16Field(0, default=0)
        data = bytes([0x01, 0x02])
        assert field.parse(data) == 0x0102
        assert field.serialize(0x0102) == data

    def test_int24_round_trip(self):
        """Test Int24Field."""
        field = Int24Field(0, default=0)
        data = bytes([0x00, 0x00, 0x05])
        assert field.parse(data) == 5
        assert field.serialize(5) == data


class TestStringField:
    """Tests for StringField."""

    def test_fixed_length_serialize(self):
        """Test fixed-length string serialization."""
        field = StringField(0, length=4, default="")
        assert field.parse(bytes([65, 66, 67, 0])) == "ABC"
        assert field.serialize("AB") == bytes([65, 66, 0, 0])


class TestRawTailField:
    """Tests for RawTailField."""

    def test_parse_tail(self):
        """Test remaining bytes parsing."""
        field = RawTailField(2)
        assert field.parse(bytes([0x01, 0x02, 0x03, 0x04])) == bytes([0x03, 0x04])


class TestComputedField:
    """Tests for ComputedField."""

    def test_parser_only(self):
        """Test computed parser."""
        field = ComputedField(parser=lambda data: data[0] * 2, default=0)
        assert field.parse(bytes([0x05])) == 10


class TestDeclarativeMessage:
    """Tests for generated DeclarativeMessage behavior."""

    def test_led_example_populate_and_binary(self):
        """Test generated from_bytes and data_to_binary."""
        msg = _LedExampleMessage.from_bytes(
            bytes([0x03]), address=0x01, priority=PRIORITY_LOW, rtr=False
        )
        assert msg.leds == [1, 2]
        assert msg.data_to_binary() == bytes([0xF6, 0x03])

    def test_led_example_parser_error_on_short_data(self):
        """Test ParserError when data is too short."""
        with pytest.raises(ParserError):
            _LedExampleMessage.from_bytes(
                bytes([]), address=0x01, priority=PRIORITY_LOW, rtr=False
            )

    def test_relay_status_example_round_trip(self):
        """Test a multi-field layout matches expected bytes."""
        msg = _RelayStatusExampleMessage.from_bytes(
            bytes([0x01, 0x00, 0x01, 0x00, 0, 0, 5]),
            address=0x01,
            priority=PRIORITY_LOW,
            rtr=False,
        )
        assert msg.channel == 1
        assert msg.delay_time == 5
        assert msg.data_to_binary() == bytes([0xFB, 0x01, 0x00, 0x01, 0x00, 0, 0, 5])

    def test_high_priority_defaults(self):
        """Test priority configuration on declarative messages."""

        class _HighPriorityMessage(DeclarativeMessage):
            _command_code = 0x02
            _priority = PRIORITY_HIGH
            _data_length = 1

            relay_channels = ChannelsField(0)

        msg = _HighPriorityMessage.from_bytes(
            bytes([0x03]), address=0x01, priority=PRIORITY_HIGH, rtr=False
        )
        assert msg.priority == PRIORITY_HIGH
        assert msg.relay_channels == [1, 2]

    def test_custom_field_parser(self):
        """Test custom parser and serializer on Field."""

        class _TemperatureSetMessage(DeclarativeMessage):
            _command_code = 0xE4
            _data_length = 1

            temp_type = ComputedField(
                parser=lambda data: 0, default=0, serializable=True
            )
            temp = Field(
                byte_index=1,
                default=0,
                parser=lambda data: data[1] * 2,
                serializer=lambda value: bytes([int(value)]),
            )

        msg = _TemperatureSetMessage.from_bytes(
            bytes([0x00, 0x0A]), address=0x01, priority=PRIORITY_LOW, rtr=False
        )
        assert msg.temp == 20
        assert msg.data_to_binary() == bytes([0xE4, 0, 20])

    def test_optional_to_json_generation(self):
        """Test optional generated to_json with map support."""

        class _StatusMessage(DeclarativeMessage):
            _command_code = 0xEA
            _priority = None
            _data_length = 1
            _generates_data_to_binary = False
            _generates_to_json = True

            status = BitField(
                0,
                bit_range=(1, 2),
                default=0,
                serializable=False,
                json_map={0: "run", 1: "manual"},
            )

        msg = _StatusMessage.from_bytes(
            bytes([0x02]), address=0x01, priority=PRIORITY_LOW, rtr=False
        )
        result = json.loads(msg.to_json())
        assert result["status"] == "manual"

    def test_bitfield_explicit_bit_and_bit_range(self):
        """Test BitField with explicit bit and bit_range parameters."""
        f_single = BitField(0, bit=7)
        assert f_single.mask == 0x80
        assert f_single.shift == 7
        assert f_single.as_bool is True
        assert f_single.parse(bytes([0x80])) is True
        assert f_single.serialize(True) == bytes([0x80])

        f_range = BitField(0, bit_range=(5, 6))
        assert f_range.mask == 0x60
        assert f_range.shift == 5
        assert f_range.as_bool is False
        assert f_range.parse(bytes([0x60])) == 3
        assert f_range.serialize(3) == bytes([0x60])

        f_start_count = BitField(0, bit_start=1, bit_count=3)
        assert f_start_count.mask == 0x0E
        assert f_start_count.shift == 1

    def test_bitfield_invalid_parameters_raise(self):
        """Test invalid bit parameters raise ValueError."""
        with pytest.raises(ValueError, match="byte_index must be >= 0"):
            BitField(-1, bit=0)

        with pytest.raises(ValueError, match="Must specify exactly one of"):
            BitField(0)

        with pytest.raises(ValueError, match="Must specify exactly one of"):
            BitField(0, bit=0, bit_range=(0, 1))

        with pytest.raises(ValueError, match="bit must be between 0 and 7"):
            BitField(0, bit=8)

        with pytest.raises(ValueError, match="bit_range must satisfy"):
            BitField(0, bit_range=(5, 3))

        with pytest.raises(ValueError, match="bit_range must satisfy"):
            BitField(0, bit_range=(0, 8))

        with pytest.raises(ValueError, match="bit_start must be between 0 and 7"):
            BitField(0, bit_start=8, bit_count=1)

        with pytest.raises(ValueError, match="bit_count must be between 1 and 2"):
            BitField(0, bit_start=6, bit_count=3)

    def test_overlapping_bitfields_raise(self):
        """Test defining overlapping BitFields on a message class raises TypeError."""
        with pytest.raises(
            TypeError,
            match="Overlapping bitfields on byte 0 in _BadMsg: field 'flag_b'",
        ):

            class _BadMsg(DeclarativeMessage):
                _command_code = 0x01
                flag_a = BitField(0, bit_range=(0, 2))
                flag_b = BitField(0, bit=2)


class TestMessageValidation:
    """Tests for Message input validation."""

    def test_invalid_address_raises_value_error(self):
        """Address outside 0..255 or non-int must raise ValueError."""
        with pytest.raises(
            ValueError, match="Address must be an integer between 0 and 255"
        ):
            Message(address=256)

        with pytest.raises(
            ValueError, match="Address must be an integer between 0 and 255"
        ):
            Message(address=-1)

        with pytest.raises(
            ValueError, match="Address must be an integer between 0 and 255"
        ):
            Message(address="0x01")  # type: ignore[arg-type]

    def test_invalid_priority_raises_value_error(self):
        """Raw int or non-MessagePriority enum must raise ValueError."""
        with pytest.raises(ValueError, match="Priority must be a MessagePriority enum"):
            Message(priority=0xFB)  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="Priority must be a MessagePriority enum"):
            Message(priority="high")  # type: ignore[arg-type]
