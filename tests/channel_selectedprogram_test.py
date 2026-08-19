"""Test cases for the SelectedProgram channel class"""

from unittest.mock import Mock, patch

import pytest

from velbusaio.messages.module_status import PROGRAM_SELECTION
from velbusaio.messages.select_program import SelectProgramMessage
from velbusaio.properties import SelectedProgram


class TestSelectedProgram:
    """Test cases for the SelectedProgram channel class."""

    def test_get_categories(self, mock_module, mock_writer):
        """Test selected program categories."""
        prog = SelectedProgram(mock_module, "Program")
        assert prog.get_categories() == ["select"]

    def test_options(self, mock_module, mock_writer):
        """Test getting available program options."""
        prog = SelectedProgram(mock_module, "Program")
        assert prog.options == list(PROGRAM_SELECTION.values())

    @pytest.mark.asyncio
    async def test_selected_program_value(self, mock_module, mock_writer):
        """Test getting selected program value."""
        prog = SelectedProgram(mock_module, "Program")
        await prog.update_value("Program 1")
        assert prog.value == "Program 1"

    @pytest.mark.asyncio
    async def test_set_selected_program(self, mock_module, mock_writer):
        """Test setting selected program."""
        prog = SelectedProgram(mock_module, "Program")
        program_name = list(PROGRAM_SELECTION.values())[0]
        await prog.set(program_name)

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, SelectProgramMessage)
        assert sent_msg.select_program == list(PROGRAM_SELECTION.keys())[0]
        assert prog.value == program_name
