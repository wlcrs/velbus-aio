"""Test cases for the base Channel class"""

import pytest

from velbusaio.channels import Channel


class TestChannel:
    """Test cases for the base Channel class."""

    def test_init_with_editable_name(self, mock_module):
        """Test channel initialization with editable name."""
        channel = Channel(mock_module, 1, "Test Channel", True, True, 0x01)
        assert channel.channel_number == 1
        assert channel.name == "Test Channel"
        assert channel.default_name == "Test Channel"
        assert channel.sub_device

    def test_init_with_non_editable_name(self, mock_module):
        """Test channel initialization with non-editable name."""
        channel = Channel(
            mock_module, 1, "Test Channel", False, False, 0x01
        )
        assert not channel.sub_device

    def test_module_property_access(self, mock_module):
        """Test accessing module via property."""
        channel = Channel(mock_module, 1, "Test", False, False, 0x01)
        assert channel.module is mock_module
        assert channel.module.type == 0x01
        assert channel.module.type_name == "TestModule"
        assert channel.module.serial == "12345"
        assert channel.module.sw_version == "1.0.0"
        assert channel.module.address == 0x01

    def test_get_full_name_subdevice(self, mock_module):
        """Test getting full name for subdevice."""
        channel = Channel(mock_module, 1, "Channel 1", False, True, 0x01)
        assert channel.full_name == "Test Module Name (TestModule) - Channel 1"

    def test_get_full_name_not_subdevice(self, mock_module):
        """Test getting full name for non-subdevice."""
        channel = Channel(mock_module, 1, "Channel 1", False, False, 0x01)
        assert channel.full_name == "Test Module Name (TestModule)"

    def test_set_name_char(self, mock_module):
        """Test setting individual characters in channel name."""
        channel = Channel(mock_module, 1, "Test", False, False, 0x01)
        channel.set_name_char(0, ord("H"))
        channel.set_name_char(1, ord("e"))
        channel.set_name_char(2, ord("l"))
        channel.set_name_char(3, ord("l"))
        channel.set_name_char(4, ord("o"))
        assert channel.name == "Hello"

    def test_set_name_char_extends_string(self, mock_module):
        """Test that set_name_char extends string with spaces if needed."""
        channel = Channel(mock_module, 1, "Hi", False, False, 0x01)
        channel.set_name_char(5, ord("!"))
        assert len(channel.name) >= 6
        assert channel.name[5] == "!"

    def test_set_name_part(self, mock_module):
        """Test setting name parts."""
        channel = Channel(mock_module, 1, "Test", True, False, 0x01)
        channel.set_name_part(1, "Hello")
        channel.set_name_part(2, "World")
        channel.set_name_part(3, "!")
        assert channel.name == "HelloWorld!"

    def test_get_channel_info(self, mock_module):
        """Test getting channel info dictionary."""
        channel = Channel(mock_module, 1, "Test", False, False, 0x01)
        info = channel.get_channel_info()
        assert info["type"] == "Channel"
        assert info["channel_number"] == 1
        assert info["name"] == "Test"
        assert "_module" not in info
        assert "_writer" not in info

    @pytest.mark.asyncio
    async def test_update(self, mock_module):
        """Test updating channel attributes."""
        from unittest.mock import AsyncMock

        channel = Channel(mock_module, 1, "Test", False, False, 0x01)
        callback = AsyncMock()
        channel.on_status_update(callback)

        channel.name = "Updated Name"
        channel._is_dirty = True
        await channel.maybe_status_update()
        assert channel.name == "Updated Name"
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_no_change(self, mock_module):
        """Test update with no actual change doesn't trigger callback."""
        from unittest.mock import AsyncMock

        channel = Channel(mock_module, 1, "Test", False, False, 0x01)
        callback = AsyncMock()
        channel.on_status_update(callback)

        await channel.maybe_status_update()
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_dirty_tracking_with_annotations(self, mock_module):
        """Test that assigning to tracked annotated fields marks item dirty."""
        from unittest.mock import AsyncMock

        class CustomItem(Channel):
            val: int = 0

        item = CustomItem(mock_module, 1, "Test", False, False, 0x01)
        callback = AsyncMock()
        item.on_status_update(callback)

        # No change
        await item.maybe_status_update()
        callback.assert_not_called()

        # Change val
        item.val = 42
        assert item._is_dirty is True
        await item.maybe_status_update()
        callback.assert_called_once()
        assert item._is_dirty is False

        # Assign same value again -> should not become dirty
        item.val = 42
        assert item._is_dirty is False
        await item.maybe_status_update()
        callback.assert_called_once()

    def test_dirty_tracking_mixin_standalone(self):
        """Test DirtyTrackingMixin on a standalone class."""
        from velbusaio.baseItem import DirtyTrackingMixin

        class Model(DirtyTrackingMixin):
            status: str = "idle"
            count: int = 0

        m = Model()
        assert m._is_dirty is False
        assert m._tracked_fields == frozenset({"status", "count"})

        m.status = "running"
        assert m._is_dirty is True
        m._is_dirty = False

        # Assign same value
        m.status = "running"
        assert m._is_dirty is False

    def test_get_categories_default(self, mock_module):
        """Test default categories returns empty list."""
        channel = Channel(mock_module, 1, "Test", False, False, 0x01)
        assert channel.get_categories() == []

    def test_on_status_update(self, mock_module):
        """Test adding status update callback."""
        from unittest.mock import AsyncMock

        channel = Channel(mock_module, 1, "Test", False, False, 0x01)
        callback = AsyncMock()
        channel.on_status_update(callback)
        assert callback in channel._on_status_update

    def test_remove_on_status_update(self, mock_module):
        """Test removing status update callback."""
        from unittest.mock import AsyncMock

        channel = Channel(mock_module, 1, "Test", False, False, 0x01)
        callback = AsyncMock()
        channel.on_status_update(callback)
        channel.remove_on_status_update(callback)
        assert callback not in channel._on_status_update

    def test_channel_protocols(self, mock_module):
        """Test that base Channel does not implement specialized protocols."""
        from velbusaio.protocols import Counter, Cover, Dimmable, HasEnergy, HasUnit, Pressable, Switchable, Temperature

        channel = Channel(mock_module, 1, "Test", False, False, 0x01)
        assert not isinstance(channel, Counter)
        assert not isinstance(channel, Temperature)
        assert not isinstance(channel, HasUnit)
        assert not isinstance(channel, Pressable)
        assert not isinstance(channel, HasEnergy)
        assert not isinstance(channel, Switchable)
        assert not isinstance(channel, Dimmable)
        assert not isinstance(channel, Cover)

    def test_to_cache(self, mock_module):
        """Test converting channel to cache dictionary."""
        channel = Channel(mock_module, 1, "Test", False, True, 0x01)
        cache = channel.to_cache()
        assert cache["name"] == "Test"
        assert cache["type"] == "Channel"
        assert cache["subdevice"] is True

    @pytest.mark.asyncio
    async def test_set_name_persistent(self, mock_module):
        """Test persistent channel renaming writes EEPROM and updates cache."""
        from unittest.mock import AsyncMock

        memory = AsyncMock()
        mock_module.memory = memory
        mock_module._channel_name_range.return_value = (0x0100, 16)
        mock_module._controller.save_module_cache = AsyncMock()

        channel = Channel(mock_module, 1, "Old Name", True, False, 0x01)
        await channel.set_name_persistent("New Name")

        assert channel.name == "New Name"
        memory.write_bytes.assert_awaited_once()
        mock_module._controller.save_module_cache.assert_awaited_once_with(mock_module)
