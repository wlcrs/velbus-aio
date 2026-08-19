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
        prog = SelectedProgram(mock_module, "Program", mock_writer)
        assert prog.get_categories() == ["select"]

    def test_get_class(self, mock_module, mock_writer):
        """Test getting selected program class."""
        prog = SelectedProgram(mock_module, "Program", mock_writer)
        assert prog.get_class() is None

    def test_get_options(self, mock_module, mock_writer):
        """Test getting available program options."""
        prog = SelectedProgram(mock_module, "Program", mock_writer)
        assert prog.get_options() == list(PROGRAM_SELECTION.values())

    @pytest.mark.asyncio
    async def test_get_selected_program(self, mock_module, mock_writer):
        """Test getting selected program."""
        prog = SelectedProgram(mock_module, "Program", mock_writer)
        await prog.update_value("Program 1")
        assert prog.get_selected_program() == "Program 1"
        assert prog.get_state() == "Program 1"

    @pytest.mark.asyncio
    async def test_set_selected_program(self, mock_module, mock_writer):
        """Test setting selected program."""
        prog = SelectedProgram(mock_module, "Program", mock_writer)
        program_name = list(PROGRAM_SELECTION.values())[0]
        await prog.set_selected_program(program_name)

        mock_writer.assert_called_once()
        sent_msg = mock_writer.call_args[0][0]
        assert isinstance(sent_msg, SelectProgramMessage)
        assert sent_msg.select_program == list(PROGRAM_SELECTION.keys())[0]
