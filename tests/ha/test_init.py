"""Tests for setting up, unloading, removing and migrating a projector entry."""

from __future__ import annotations

import socket
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.valerion.const import DOMAIN, NAVIGATION_KEYS
from custom_components.valerion.coordinator import Connection, PowerState
from tests.lib.fake_projector import FakeProjector

from .conftest import PROJECTOR_MAC


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_and_unload(
    hass: HomeAssistant, projector: FakeProjector, mock_config_entry: MockConfigEntry
) -> None:
    await _setup(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    data = mock_config_entry.runtime_data.data
    assert data.connection == Connection.ANSWERING
    assert data.power == PowerState.ON
    assert hass.services.has_service(DOMAIN, "send_raw_command")

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_when_awol_link_is_off(hass: HomeAssistant, socket_enabled: None) -> None:
    # A closed port behaves like a projector with AWOL Link switched off.
    # Setup must still succeed: it is a state to show, not a broken entry.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: closed_port},
        version=1,
        minor_version=2,
    )
    await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.data.connection == Connection.REFUSED


async def test_remove_deletes_learned_locks(
    hass: HomeAssistant,
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    await _setup(hass, mock_config_entry)
    store_key = f"{DOMAIN}.{mock_config_entry.entry_id}.locks"
    # Learning a lock writes the store; force it here.
    await mock_config_entry.runtime_data._lock_store.async_save({"learned": {}})
    assert store_key in hass_storage

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert store_key not in hass_storage


def _old_entry(port: int, *, pref_disable_new_entities: bool = False) -> MockConfigEntry:
    """A config entry as v0.0.10 and older created it (minor version 1)."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        unique_id=PROJECTOR_MAC,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: port},
        version=1,
        minor_version=1,
        pref_disable_new_entities=pref_disable_new_entities,
    )


def _register_buttons(
    entity_registry: er.EntityRegistry,
    entry: MockConfigEntry,
    disabled_by: dict[str, er.RegistryEntryDisabler],
) -> None:
    """Create the registry entries a v0.0.10 install left behind."""
    for key in (*NAVIGATION_KEYS, "forget_learned_locks"):
        unique_id = (
            f"{PROJECTOR_MAC}_{key}"
            if key == "forget_learned_locks"
            else f"{PROJECTOR_MAC}_button_{key}"
        )
        entity_registry.async_get_or_create(
            "button",
            DOMAIN,
            unique_id,
            config_entry=entry,
            suggested_object_id=f"living_room_{key}",
            disabled_by=disabled_by.get(key, er.RegistryEntryDisabler.INTEGRATION),
        )


def _disabled_by(entity_registry: er.EntityRegistry, key: str) -> er.RegistryEntryDisabler | None:
    entity_id = entity_registry.async_get_entity_id("button", DOMAIN, f"{PROJECTOR_MAC}_{key}")
    assert entity_id is not None
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    return entry.disabled_by


async def test_migration_enables_key_buttons(
    hass: HomeAssistant,
    projector: FakeProjector,
    entity_registry: er.EntityRegistry,
) -> None:
    entry = _old_entry(projector.port)
    entry.add_to_hass(hass)
    _register_buttons(entity_registry, entry, {"down": er.RegistryEntryDisabler.USER})

    await _setup(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert _disabled_by(entity_registry, "button_up") is None
    assert _disabled_by(entity_registry, "button_home") is None
    # Disabled by the user: stays disabled.
    assert _disabled_by(entity_registry, "button_down") is er.RegistryEntryDisabler.USER
    # Not a key button: disabled by default, untouched.
    assert (
        _disabled_by(entity_registry, "forget_learned_locks")
        is er.RegistryEntryDisabler.INTEGRATION
    )


async def test_migration_respects_disabled_new_entities(
    hass: HomeAssistant,
    projector: FakeProjector,
    entity_registry: er.EntityRegistry,
) -> None:
    # With "Enable newly added entities" off, Home Assistant itself marks new
    # entities as disabled by the integration, so they must stay disabled.
    entry = _old_entry(projector.port, pref_disable_new_entities=True)
    entry.add_to_hass(hass)
    _register_buttons(entity_registry, entry, {})

    await _setup(hass, entry)

    assert entry.minor_version == 2
    for key in NAVIGATION_KEYS:
        assert _disabled_by(entity_registry, f"button_{key}") is (
            er.RegistryEntryDisabler.INTEGRATION
        )


async def test_no_migration_for_current_entries(
    hass: HomeAssistant,
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    # A current entry whose key button was disabled by the integration on
    # purpose (for example the system option) is left alone.
    mock_config_entry.add_to_hass(hass)
    _register_buttons(entity_registry, mock_config_entry, {})

    await _setup(hass, mock_config_entry)

    assert mock_config_entry.minor_version == 2
    assert _disabled_by(entity_registry, "button_up") is er.RegistryEntryDisabler.INTEGRATION
