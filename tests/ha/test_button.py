"""Tests for the key and lens menu buttons and the forget-learned-locks button."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from custom_components.valerion.coordinator import ValerionCoordinator
from custom_components.valerion.lib import key_press
from tests.lib.fake_projector import FakeProjector

from .conftest import entity_id, poll, setup_entry

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")


async def _press(hass: HomeAssistant, key: str) -> None:
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id(hass, BUTTON_DOMAIN, key)},
        blocking=True,
    )


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
) -> None:
    with patch("custom_components.valerion.PLATFORMS", [Platform.BUTTON]):
        await setup_entry(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_press_keys(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    await _press(hass, "button_up")
    await _press(hass, "button_zoom")
    assert key_press("up").line in projector.received
    assert "%3ZMMN ?" in projector.received


async def test_unsupported_lens_menu_hides_itself(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
) -> None:
    # A Pro2 has no motorised lens shift: the menu answers ERR3 while on.
    projector.unavailable.add("%3LSMN")
    lens_shift = entity_id(hass, BUTTON_DOMAIN, "button_lens_shift")
    with pytest.raises(HomeAssistantError) as err:
        await _press(hass, "button_lens_shift")
    assert err.value.translation_key == "lens_menu_unsupported"
    await hass.async_block_till_done()

    assert hass.states.get(lens_shift).state == STATE_UNAVAILABLE
    assert entity_registry.async_get(lens_shift).hidden_by is er.RegistryEntryHider.INTEGRATION
    # The other menus stay.
    assert hass.states.get(entity_id(hass, BUTTON_DOMAIN, "button_zoom")).state == STATE_UNKNOWN

    # Forget learned locks brings it back.
    await _press(hass, "forget_learned_locks")
    await hass.async_block_till_done()
    # A button's state is the time it was last pressed.
    assert hass.states.get(lens_shift).state != STATE_UNAVAILABLE
    assert entity_registry.async_get(lens_shift).hidden_by is None


async def test_user_hidden_menu_is_left_alone(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
) -> None:
    lens_shift = entity_id(hass, BUTTON_DOMAIN, "button_lens_shift")
    entity_registry.async_update_entity(lens_shift, hidden_by=er.RegistryEntryHider.USER)
    projector.unavailable.add("%3LSMN")
    with pytest.raises(HomeAssistantError):
        await _press(hass, "button_lens_shift")
    await coordinator.async_forget_locks()
    await hass.async_block_till_done()
    assert entity_registry.async_get(lens_shift).hidden_by is er.RegistryEntryHider.USER


async def test_menu_learned_before_restart_stays_hidden(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
    mock_config_entry: MockConfigEntry,
) -> None:
    projector.unavailable.add("%3FCMN")
    with pytest.raises(HomeAssistantError):
        await _press(hass, "button_focus")
    # Write the learned menu as Home Assistant does when it shuts down.
    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    focus = entity_id(hass, BUTTON_DOMAIN, "button_focus")
    assert hass.states.get(focus).state == STATE_UNAVAILABLE
    assert entity_registry.async_get(focus).hidden_by is er.RegistryEntryHider.INTEGRATION


async def test_forget_locks_available_in_standby(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # The locks live in Home Assistant, so the button works with the projector off.
    projector.values["%1POWR"] = "0"
    await poll(hass, coordinator)
    assert hass.states.get(entity_id(hass, BUTTON_DOMAIN, "button_up")).state == (STATE_UNAVAILABLE)
    forget = entity_id(hass, BUTTON_DOMAIN, "forget_learned_locks")
    assert hass.states.get(forget).state == STATE_UNKNOWN
    await _press(hass, "forget_learned_locks")
