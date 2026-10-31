"""Tests for the media player: power, input, volume and mute."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOURCE,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_MAC,
    CONF_PORT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_OFF,
    STATE_ON,
    STATE_STANDBY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from custom_components.valerion.const import DOMAIN
from custom_components.valerion.coordinator import ValerionCoordinator
from custom_components.valerion.lib import AwolLinkConnectionError
from tests.lib.fake_projector import FakeProjector

from .conftest import ENTRY_ID, PROJECTOR_MAC, entity_id, poll, setup_entry


async def _call(hass: HomeAssistant, service: str, **data: object) -> None:
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id(hass, MEDIA_PLAYER_DOMAIN, "media_player"), **data},
        blocking=True,
    )


def _state(hass: HomeAssistant) -> State:
    state = hass.states.get(entity_id(hass, MEDIA_PLAYER_DOMAIN, "media_player"))
    assert state is not None
    return state


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
) -> None:
    with patch("custom_components.valerion.PLATFORMS", [Platform.MEDIA_PLAYER]):
        await setup_entry(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_state_and_attributes(hass: HomeAssistant, coordinator: ValerionCoordinator) -> None:
    state = _state(hass)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INPUT_SOURCE] == "HDMI 1"
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["Home", "HDMI 1", "HDMI 2", "HDMI 3"]
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.35
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False
    assert state.attributes["power_state"] == "on"
    assert state.attributes["connection"] == "answering"


async def test_unknown_power_and_volume_values(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # Values outside the command list are shown as unknown, never as a guess.
    projector.values["%3VOLM"] = "loud"
    await poll(hass, coordinator)
    assert ATTR_MEDIA_VOLUME_LEVEL not in _state(hass).attributes

    projector.values["%1POWR"] = "7"
    await poll(hass, coordinator)
    state = _state(hass)
    assert state.state == STATE_UNKNOWN
    assert state.attributes["power_state"] is None


async def test_select_source(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    await _call(hass, SERVICE_SELECT_SOURCE, source="HDMI 2")
    assert "%2INPT 32" in projector.received
    assert _state(hass).attributes[ATTR_INPUT_SOURCE] == "HDMI 2"

    with pytest.raises(ServiceValidationError):
        await _call(hass, SERVICE_SELECT_SOURCE, source="Netflix")


async def test_volume_and_mute(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    await _call(hass, SERVICE_VOLUME_SET, volume_level=0.5)
    assert "%3VOLM 50" in projector.received
    assert _state(hass).attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.5

    await _call(hass, SERVICE_VOLUME_UP)
    await _call(hass, SERVICE_VOLUME_DOWN)
    assert projector.received.count("%2SVOL 1") == 1
    assert projector.received.count("%2SVOL 0") == 1

    await _call(hass, SERVICE_VOLUME_MUTE, is_volume_muted=True)
    assert "%1AVMT 21" in projector.received
    assert _state(hass).attributes[ATTR_MEDIA_VOLUME_MUTED] is True


async def test_turn_off_and_on(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    await _call(hass, SERVICE_TURN_OFF)
    assert "%1POWR 0" in projector.received
    assert _state(hass).state == STATE_STANDBY
    await hass.async_block_till_done(wait_background_tasks=True)

    await _call(hass, SERVICE_TURN_ON)
    assert "%1POWR 1" in projector.received
    await poll(hass, coordinator)
    assert _state(hass).state == STATE_ON


async def test_assumed_state_while_busy(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    coordinator.client.timeout = 0.1
    projector.silent = True
    await poll(hass, coordinator)
    state = _state(hass)
    assert state.state == STATE_ON
    assert state.attributes[ATTR_ASSUMED_STATE] is True
    assert state.attributes["busy"] is True


async def test_unreachable_without_mac_is_unavailable(
    hass: HomeAssistant, coordinator: ValerionCoordinator
) -> None:
    # Without a MAC address nothing can switch it on, so there is nothing to offer.
    with patch.object(coordinator.client, "_open", side_effect=AwolLinkConnectionError("down")):
        await poll(hass, coordinator)
    assert _state(hass).state == STATE_UNAVAILABLE


async def test_unreachable_with_mac_is_off(hass: HomeAssistant, projector: FakeProjector) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        unique_id=PROJECTOR_MAC,
        entry_id=ENTRY_ID,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: projector.port, CONF_MAC: PROJECTOR_MAC},
        version=1,
        minor_version=2,
    )
    await setup_entry(hass, entry)
    coordinator: ValerionCoordinator = entry.runtime_data
    with patch.object(coordinator.client, "_open", side_effect=AwolLinkConnectionError("down")):
        await poll(hass, coordinator)
    assert _state(hass).state == STATE_OFF


async def test_awol_link_off_is_unavailable(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    await projector.stop()
    await poll(hass, coordinator)
    assert _state(hass).state == STATE_UNAVAILABLE
