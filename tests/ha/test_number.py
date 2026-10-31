"""Tests for the laser level number."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from custom_components.valerion.coordinator import ValerionCoordinator
from tests.lib.fake_projector import FakeProjector

from .conftest import entity_id, poll_settings, setup_entry


async def _set(hass: HomeAssistant, value: float) -> None:
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id(hass, NUMBER_DOMAIN, "laser_level"), ATTR_VALUE: value},
        blocking=True,
    )


def _state(hass: HomeAssistant) -> str:
    state = hass.states.get(entity_id(hass, NUMBER_DOMAIN, "laser_level"))
    assert state is not None
    return state.state


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
) -> None:
    with patch("custom_components.valerion.PLATFORMS", [Platform.NUMBER]):
        await setup_entry(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_laser_level(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    assert _state(hass) == "7"
    await _set(hass, 5)
    assert "%3LASL 5" in projector.received
    assert _state(hass) == "5"


async def test_learned_lock(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.refused["%3LASL"] = "ERR3"
    with pytest.raises(HomeAssistantError):
        await _set(hass, 5)
    assert _state(hass) == STATE_UNAVAILABLE


async def test_unreadable_value(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.values["%3LASL"] = "high"
    await poll_settings(hass, coordinator)
    assert _state(hass) == STATE_UNKNOWN
