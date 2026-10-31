"""Tests for the problem binary sensor."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from custom_components.valerion.coordinator import ValerionCoordinator
from tests.lib.fake_projector import FakeProjector

from .conftest import entity_id, poll_settings, setup_entry


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
) -> None:
    with patch("custom_components.valerion.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_entry(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("led_status", "expected"),
    [("0", STATE_OFF), ("1", STATE_ON), ("3", STATE_ON), ("9", STATE_ON)],
)
async def test_problem(
    hass: HomeAssistant,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
    led_status: str,
    expected: str,
) -> None:
    # Every code except 0 is a problem, including undocumented ones.
    projector.values["%3LEDS"] = led_status
    await poll_settings(hass, coordinator)
    assert hass.states.get(entity_id(hass, BINARY_SENSOR_DOMAIN, "problem")).state == expected
