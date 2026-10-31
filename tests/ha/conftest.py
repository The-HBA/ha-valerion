"""Fixtures for the Home Assistant level tests.

The integration talks to the same scripted fake projector as the library
tests, on 127.0.0.1 (the only address the test harness lets sockets reach).
So setup runs through the real client and coordinator, not a mock.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from homeassistant.const import CONF_HOST, CONF_PORT
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.valerion.const import DOMAIN
from tests.lib.fake_projector import DEFAULT_VALUES, FakeProjector

PROJECTOR_MAC = "f0:ed:51:c4:4c:a8"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
async def projector(socket_enabled: None) -> AsyncIterator[FakeProjector]:
    """A running fake projector that is on, without security code.

    The test harness blocks network sockets; ``socket_enabled`` allows them
    again, still limited to 127.0.0.1.
    """
    fake = FakeProjector(values=dict(DEFAULT_VALUES))
    await fake.start()
    yield fake
    await fake.stop()


@pytest.fixture
def mock_config_entry(projector: FakeProjector) -> MockConfigEntry:
    """A config entry for the fake projector, as the current version creates it."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        unique_id=PROJECTOR_MAC,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: projector.port},
        version=1,
        minor_version=2,
    )
