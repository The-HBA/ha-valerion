"""Tests for the remote entity: key presses by name, power."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.remote import (
    ATTR_COMMAND,
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from custom_components.valerion.coordinator import ValerionCoordinator
from custom_components.valerion.lib import key_press
from tests.lib.fake_projector import FakeProjector

from .conftest import entity_id, poll, setup_entry


async def _call(hass: HomeAssistant, service: str, **data: object) -> None:
    await hass.services.async_call(
        REMOTE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id(hass, REMOTE_DOMAIN, "remote"), **data},
        blocking=True,
    )


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
) -> None:
    with patch("custom_components.valerion.PLATFORMS", [Platform.REMOTE]):
        await setup_entry(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_send_command(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.received.clear()
    await _call(
        hass,
        SERVICE_SEND_COMMAND,
        **{ATTR_COMMAND: ["down", "OK"], ATTR_NUM_REPEATS: 2, ATTR_DELAY_SECS: 0},
    )
    down, ok = key_press("down").line, key_press("ok").line
    sent = [line for line in projector.received if not line.endswith(" ?")]
    assert sent == [down, ok, down, ok]


async def test_send_unknown_key(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.received.clear()
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, SERVICE_SEND_COMMAND, **{ATTR_COMMAND: ["up", "eject"]})
    assert err.value.translation_key == "invalid_key"
    assert projector.received == []


async def test_send_command_in_standby(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.values["%1POWR"] = "0"
    await poll(hass, coordinator)
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, SERVICE_SEND_COMMAND, **{ATTR_COMMAND: ["up"]})
    assert err.value.translation_key == "projector_off"


async def test_turn_off_and_on(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    remote = entity_id(hass, REMOTE_DOMAIN, "remote")
    assert hass.states.get(remote).state == STATE_ON

    await _call(hass, SERVICE_TURN_OFF)
    assert "%1POWR 0" in projector.received
    assert hass.states.get(remote).state == STATE_OFF
    await hass.async_block_till_done(wait_background_tasks=True)

    await _call(hass, SERVICE_TURN_ON)
    assert "%1POWR 1" in projector.received
    await poll(hass, coordinator)
    assert hass.states.get(remote).state == STATE_ON
