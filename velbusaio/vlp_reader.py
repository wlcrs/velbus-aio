"""VlpReader class.

Handles reading and parsing Velbus VLP files.
"""

import logging
from typing import TYPE_CHECKING

import anyio
from bs4 import BeautifulSoup

from velbusaio.command_registry import MODULE_DIRECTORY
from velbusaio.module_spec_loader import load_module_spec

if TYPE_CHECKING:
    from velbusaio.controller import Controller
    from velbusaio.module import Module


async def create_module_from_vlp(
    vlp_mod: vlpModule, *, controller: Controller
) -> Module:
    """Construct and populate a Module instance from parsed VLP module data."""
    from velbusaio.module import Module  # noqa: PLC0415

    addr = vlp_mod.get_decimal_addr()
    mod_type = vlp_mod.get_type()
    if mod_type is None:
        raise ValueError(f"Unknown module type for VLP module {vlp_mod.get_name()}")

    build = vlp_mod.get_build()
    build_year = int(build[:2]) if len(build) >= 4 and build[:2].isdigit() else None
    build_week = int(build[2:4]) if len(build) >= 4 and build[2:4].isdigit() else None

    module = Module.factory(
        addr,
        mod_type,
        controller=controller,
        serial=vlp_mod.get_serial(),
        build_year=build_year,
        build_week=build_week,
    )
    module._name = vlp_mod.get_name()  # noqa: SLF001
    for chan_addr, chan_info in vlp_mod.get_channels().items():
        try:
            chan_num = int(chan_addr)
        except ValueError:
            continue
        if chan_num in module._channels and isinstance(chan_info, dict):  # noqa: SLF001
            if "Name" in chan_info:
                module._channels[chan_num].name = chan_info["Name"]  # noqa: SLF001
            unit = chan_info.get("Unit")
            if unit and unit != "reserved":
                from velbusaio.channels import CounterChannel  # noqa: PLC0415

                existing_chan = module._channels[chan_num]  # noqa: SLF001
                counter = CounterChannel(
                    module=module,
                    num=chan_num,
                    name=existing_chan.name,
                    nameEditable=True,
                    subDevice=existing_chan.is_sub_device(),
                    address=addr,
                )
                counter.set_unit(unit)
                module._channels[chan_num] = counter  # noqa: SLF001
    return module


class VlpFile:
    """VLP file reader and parser."""

    def __init__(self, file_path) -> None:
        """Initialize VLP file reader."""
        self._file_path = file_path
        self._modules = []
        self._log = logging.getLogger("velbus-vlpFile")

    def get(self) -> list:
        """Return the parsed modules."""
        return self._modules

    async def read(self) -> None:
        """Read and parse the VLP file."""
        async with await anyio.open_file(self._file_path) as file:
            xml_content = await file.read()
        _soup = BeautifulSoup(xml_content, "xml")
        for module in _soup.find_all("Module"):
            caption_tag = module.find("Caption")
            memory_tag = module.find("Memory")
            assert caption_tag is not None
            assert memory_tag is not None
            mod = vlpModule(
                caption_tag.get_text(),
                module["address"],
                module["build"],
                module["serial"],
                module["type"],
                memory_tag.get_text(),
            )
            self._modules.append(mod)
            await mod.parse()
        self._modules.sort(key=lambda mod: mod.get_decimal_addr())

    # def dump(self) -> None:
    #    """Dump the parsed modules to the log."""
    #    for m in self._modules:
    #        print(f"Module {m.get_decimal_addr()}: {m._name}, type {m._type_id}")
    #        for key, value in m._channels.items():
    #            name = value["Name"]
    #            print(f"  {key} => {name}")


class vlpModule:
    """VLP module representation."""

    def __init__(self, name, addresses, build, serial, module_type, memory) -> None:
        """Initialize VLP module."""
        self._name = name
        self._addresses = addresses
        self._build = build
        self._serial = serial
        self._type = module_type
        self._memory = memory
        self._spec = {}
        self._channels = {}
        self._type_id = next(
            (key for key, value in MODULE_DIRECTORY.items() if value == self._type),
            None,
        )
        self._log = logging.getLogger("velbus-vlpFile")
        self._log.info(
            f"=> Created vlpModule address: {self._addresses} type: {self._type} ({self._type_id})"
        )

    def get_addr(self) -> str:
        """Get module address."""
        return self._addresses

    def get_name(self) -> str:
        """Get module name."""
        return self._name

    def get_type(self) -> int | None:
        """Get module type ID."""
        return self._type_id

    def get_serial(self) -> str:
        """Get module serial number."""
        return self._serial

    def get_memory(self) -> str:
        """Get module memory."""
        return self._memory

    def get_build(self) -> str:
        """Get module build."""
        return self._build

    def get_channels(self) -> dict:
        """Get module channels."""
        return self._channels

    def __str__(self):
        """String representation of the module."""
        return f"vlpModule(name={self._name}, addresses={self._addresses}, build={self._build}, serial={self._serial}, type={self._type})"

    def get_decimal_addr(
        self,
    ) -> int:
        """Get decimal primary module address."""
        addr = self._addresses.split(",")[0]
        return int(addr, 16)

    async def parse(self) -> None:
        """Parse the VLP module memory and extract channel names."""
        await self._load_module_spec()

        if not self._spec.memory.channels and not self._spec.memory.extras:
            self._log.debug("  => no Memory locations found")
            return

        # channel names
        self._channels = {
            num: {
                "Name": chan_spec.name,
                "Editable": "yes" if chan_spec.editable else "no",
                "Type": chan_spec.channel_type,
            }
            for num, chan_spec in self._spec.channels.items()
        }
        for chan_num, chan in self._channels.items():
            self._log.debug(f" => Processing channel {chan_num}:")
            if chan.get("Editable") == "yes":
                self._log.debug(f"  => channel {chan_num} is editable, getting name")
                name = self._get_channel_name(int(chan_num))
                if name:
                    self._log.debug(f"  => got name '{name}' for channel {chan_num}")
                    chan["Name"] = name
                    chan["_is_loaded"] = True

        # extra
        self._load_extra_data()

    def _load_extra_data(self) -> None:
        """Load extra data from memory."""
        self._log.debug(" => Getting extra data")
        if not self._spec.memory.extras:
            self._log.debug("  => no Extra Memory locations found")
            return
        for addr, extra in self._spec.memory.extras.items():
            byte_data = bytes.fromhex(self._read_from_memory(addr))
            self._log.debug(
                f"  => got extra data {byte_data.hex().upper()} from address {addr}"
            )
            if "Translate" in extra:
                translation_found = False
                for translate_key, translate_value in extra["Translate"].items():
                    if translate_key.startswith("%"):
                        # Binary pattern matching
                        if self._match_binary_pattern(translate_key, byte_data):
                            self._log.debug(
                                f"   => Binary pattern {translate_key} matched, value: {translate_value}"
                            )
                            self._channels[translate_value["Channel"]][
                                translate_value["SubName"]
                            ] = translate_value["Value"]
                            translation_found = True
                    else:
                        # Direct value matching (existing behavior for integer keys)
                        try:
                            int_key = int(translate_key)
                            if len(byte_data) > 0 and byte_data[0] == int_key:
                                self._log.debug(
                                    f"   => Direct match for value {int_key}: {translate_value}"
                                )
                                self._channels[translate_value["Channel"]][
                                    translate_value["SubName"]
                                ] = translate_value["Value"]
                                translation_found = True
                        except ValueError:
                            # Not an integer key, skip
                            continue
                if not translation_found:
                    self._log.error(
                        f" => No translation found for data {byte_data.hex().upper()}"
                    )

    def _match_binary_pattern(self, pattern: str, byte_data: bytes) -> bool:
        """Match a binary pattern like %......00 against byte data.

        % indicates binary pattern
        . means don't care bit
        0/1 are specific bits that must match
        """
        if not pattern.startswith("%"):
            return False

        # Remove the % prefix
        binary_pattern = pattern[1:]

        # Convert byte_data to binary string (without '0b' prefix)
        if len(byte_data) == 0:
            return False

        # Take the first byte for pattern matching
        byte_value = byte_data[0]
        binary_data = format(byte_value, "08b")

        # Check if pattern length matches
        if len(binary_pattern) != len(binary_data):
            return False

        # Check each bit position
        for _i, (pattern_bit, data_bit) in enumerate(
            zip(binary_pattern, binary_data, strict=True)
        ):
            if pattern_bit == ".":
                # Don't care bit, skip
                continue
            if pattern_bit != data_bit:
                # Bit mismatch
                return False

        return True

    def _get_channel_name(self, chan: int) -> str | None:
        """Get the channel name from memory."""
        self._log.debug(f" => Getting channel name for {chan}")
        if not self._spec.memory.channels:
            self._log.debug("  => no Channels Memory locations found")
            return None
        dchan = format(chan, "02d")
        if dchan not in self._spec.memory.channels:
            self._log.debug(f"  => no chan {chan} Memory locations found")
            return None
        byte_data = bytes.fromhex(
            self._read_from_memory(self._spec.memory.channels[dchan]).replace(
                "FF", ""
            )
        )
        try:
            name = byte_data.decode("ascii")
        except UnicodeDecodeError as e:
            self._log.error(f"  => UnicodeDecodeError: {e}")
            return None
        return name

    async def _load_module_spec(self) -> None:
        """Load the module specification JSON based on type ID."""
        self._log.debug(f" => Load module spec for {self._type_id}")

        # remap VMBELx modules to unified memorymap based on build number
        # remap VMBELx TO VMBELx-20
        memmap_id = self._type_id
        if memmap_id == 0x34 and self._build >= "2524":  # VMBEL1
            memmap_id = 0x4F
        elif memmap_id == 0x35 and self._build >= "2524":  # VMBEL2
            memmap_id = 0x50
        elif memmap_id == 0x36 and self._build >= "2524":  # VMBEL4
            memmap_id = 0x51
        elif memmap_id == 0x37 and self._build >= "2438":  # VMBELO
            memmap_id = 0x52
        elif memmap_id == 0x38 and self._build >= "2524":  # VMBELPIR
            memmap_id = 0x5C
        if memmap_id != self._type_id:
            self._log.debug(
                f" => Load module spec for {self._type_id}, {self._build} => {memmap_id}"
            )

        assert memmap_id is not None
        self._spec = load_module_spec(memmap_id, self._log)

    def _read_from_memory(self, address_range) -> str:
        """Read a range of bytes from the module memory."""
        # Check if there are multiple ranges separated by semicolons
        if ";" in address_range:
            result = ""
            for range_part in address_range.split(";"):
                result += self._read_from_memory(range_part)
            return result
        # its a single address
        if "-" not in address_range:
            start = int(address_range, 16) * 2
            end = (int(address_range, 16) + 1) * 2
            return self._memory[start:end]
        # its a range
        start_str, end_str = address_range.split("-")
        start = int(start_str, 16) * 2
        end = (int(end_str, 16) + 1) * 2
        return self._memory[start:end]
