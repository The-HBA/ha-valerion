"""Fixtures for the Home Assistant level tests.

The integration talks to the same scripted fake projector as the library
tests, on 127.0.0.1 (the only address the test harness lets sockets reach).
So setup runs through the real client and coordinator, not a mock.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from unittest.mock import PropertyMock, patch

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.valerion.const import DOMAIN
from custom_components.valerion.coordinator import ValerionCoordinator
from tests.lib.fake_projector import DEFAULT_VALUES, FakeProjector

PROJECTOR_MAC = "f0:ed:51:c4:4c:a8"
#: Fixed so that snapshots do not change from run to run.
ENTRY_ID = "01K8VALERI0NTESTENTRY00000"

#: Replies of a VisionMaster Pro2 playing a 4K HDR10 film (values recorded
#: in docs/protocol.md): Dolby Audio, 10-bit, YUV 4:2:2, BT.2020.
PROJECTOR_VALUES = {
    **DEFAULT_VALUES,
    "%1CLSS": "2",
    "%2INST": "30 31 32 33",
    "%2RRES": "3840 x 2160",
    "%2IRES": "3840 x 2160",
    "%3SINF": "3840*2160p@24Hz 3 2 1 1 2",
    "%3GAMA": "4",
    "%3DYTM": "1",
    "%3CLTP": "2",
    "%3ENBL": "1",
    "%3MOTN": "0",
    "%3ASPR": "3",
    "%3FANS": "1770 1710 0 0 0 0 0",
    "%3TEMP": "33 48 0 0 0 0 0 0",
    "%3LEDS": "0",
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def entity_registry_enabled_by_default() -> Iterator[None]:
    """Create entities that are disabled by default as enabled (as in Home Assistant core)."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
        new_callable=PropertyMock,
    ):
        yield


@pytest.fixture
async def projector(socket_enabled: None) -> AsyncIterator[FakeProjector]:
    """A running fake projector that is on, without security code.

    The test harness blocks network sockets; ``socket_enabled`` allows them
    again, still limited to 127.0.0.1.
    """
    fake = FakeProjector(values=dict(PROJECTOR_VALUES))
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
        entry_id=ENTRY_ID,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: projector.port},
        version=1,
        minor_version=2,
    )


@pytest.fixture
async def coordinator(
    hass: HomeAssistant, projector: FakeProjector, mock_config_entry: MockConfigEntry
) -> ValerionCoordinator:
    """The integration set up with every entity added and polled once.

    The first poll runs before any entity exists, so only the second one
    reads what the entities asked for (picture settings, signal, fans).
    """
    await setup_entry(hass, mock_config_entry)
    return mock_config_entry.runtime_data


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up ``entry`` and poll once more so the entities have their values."""
    if hass.config_entries.async_get_entry(entry.entry_id) is None:
        entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await poll(hass, entry.runtime_data)


async def poll(hass: HomeAssistant, coordinator: ValerionCoordinator, times: int = 1) -> None:
    """Run ``times`` regular polls, as the update interval would."""
    for _ in range(times):
        await coordinator.async_refresh()
    await hass.async_block_till_done()


async def poll_settings(hass: HomeAssistant, coordinator: ValerionCoordinator) -> None:
    """Poll until the slow tier (picture settings, fans, LED status) is read again."""
    await poll(hass, coordinator, times=6)


def entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    """Return the entity ID of this projector's entity with unique ID suffix ``key``."""
    found = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{PROJECTOR_MAC}_{key}")
    assert found is not None, f"no {platform} entity {key}"
    return found
