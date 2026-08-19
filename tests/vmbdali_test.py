import pytest

from velbusaio.module import VmbDali


class MockWriter:
    async def __call__(self, data):
        pass


class MockController:
    """Mock controller for testing."""

    def connected(self):
        return True

    def get_cache_dir(self):
        return None

    async def _on_modules_loaded(self, module):
        pass

    async def send(self, data):
        pass

    def _add_on_connext_callback(self, callback):
        pass

    def _remove_on_connect_callback(self, callback):
        pass

    def _add_on_disconnect_callback(self, callback):
        pass

    def _remove_on_disconnect_callback(self, callback):
        pass


@pytest.mark.asyncio
async def test_vmbdali_loads_and_has_channels():
    module_address = 0x12
    dali_type = 69
    module = VmbDali(
        module_address,
        dali_type,
        controller=MockController(),
    )

    assert len(module._channels) > 0
