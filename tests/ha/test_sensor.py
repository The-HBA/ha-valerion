"""Tests for the AWOL Link status, signal, LED, fan and temperature sensors."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from custom_components.valerion.const import DOMAIN
from custom_components.valerion.coordinator import ValerionCoordinator
from tests.lib.fake_projector import FakeProjector

from .conftest import PROJECTOR_MAC, entity_id, poll, poll_settings, setup_entry


def _state(hass: HomeAssistant, key: str) -> str:
    state = hass.states.get(entity_id(hass, SENSOR_DOMAIN, key))
    assert state is not None
    return state.state


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
) -> None:
    with patch("custom_components.valerion.PLATFORMS", [Platform.SENSOR]):
        await setup_entry(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("reply", ["0*0p@0Hz 0 255 3 0 0", "255"])
async def test_no_signal(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator, reply: str
) -> None:
    # The Pro2 on its home screen, and AWOL's documented "no signal".
    projector.values["%3SINF"] = reply
    await poll(hass, coordinator)
    assert _state(hass, "video_signal") == STATE_UNKNOWN
    assert _state(hass, "hdr_format") == "no_signal"


async def test_signal_query_refused(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.unavailable.add("%3SINF")
    await poll(hass, coordinator)
    assert _state(hass, "video_signal") == STATE_UNAVAILABLE
    assert _state(hass, "hdr_format") == STATE_UNAVAILABLE


async def test_link_status_in_every_state(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # Stays available, so the history shows how deep the projector sleeps.
    assert _state(hass, "link_status") == "answering"
    coordinator.client.timeout = 0.1
    projector.values["%1POWR"] = "0"
    projector.silent = True
    await poll(hass, coordinator)
    assert _state(hass, "link_status") == "silent"
    assert _state(hass, "video_signal") == STATE_UNAVAILABLE
    await projector.stop()
    await poll(hass, coordinator)
    assert _state(hass, "link_status") == "refused"


async def test_led_status(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.values["%3LEDS"] = "3"
    await poll_settings(hass, coordinator)
    assert _state(hass, "led_status") == "fan_error"
    # An undocumented code.
    projector.values["%3LEDS"] = "9"
    await poll_settings(hass, coordinator)
    assert _state(hass, "led_status") == STATE_UNKNOWN


async def test_new_fan_slot_adds_a_sensor(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    assert _state(hass, "fan_1") == "1770"
    assert _state(hass, "temperature_2") == "48"
    unused = er.async_get(hass).async_get_entity_id(SENSOR_DOMAIN, DOMAIN, f"{PROJECTOR_MAC}_fan_3")
    assert unused is None

    projector.values["%3FANS"] = "1770 1710 900 0 0 0 0"
    await poll_settings(hass, coordinator)
    assert _state(hass, "fan_3") == "900"


async def test_known_slots_come_back_while_off(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
) -> None:
    # After a restart with the projector in standby, slots seen before are
    # restored from the entity registry instead of disappearing.
    mock_config_entry.add_to_hass(hass)
    for key in ("fan_1", "temperature_8"):
        entity_registry.async_get_or_create(
            SENSOR_DOMAIN,
            DOMAIN,
            f"{PROJECTOR_MAC}_{key}",
            config_entry=mock_config_entry,
            suggested_object_id=f"living_room_{key}",
        )
    projector.values["%1POWR"] = "0"
    await setup_entry(hass, mock_config_entry)
    assert _state(hass, "fan_1") == STATE_UNAVAILABLE
    assert _state(hass, "temperature_8") == STATE_UNAVAILABLE

    # Slot 8 is restored but the projector reports only seven fan values.
    projector.values["%1POWR"] = "1"
    projector.values["%3TEMP"] = "33 48 0 0 0 0 0"
    await poll_settings(hass, mock_config_entry.runtime_data)
    assert _state(hass, "fan_1") == "1770"
    assert _state(hass, "temperature_8") == STATE_UNKNOWN
