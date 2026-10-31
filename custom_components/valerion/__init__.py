"""The Valerion integration: local control of Valerion projectors over AWOL Link."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import CONF_SECURITY_CODE, DOMAIN, NAVIGATION_KEYS
from .coordinator import ValerionConfigEntry, ValerionCoordinator, configured_mac, lock_store
from .lib import AwolLinkClient
from .services import async_setup_services

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.REMOTE,
    Platform.SELECT,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions once, independent of any projector being set up."""
    async_setup_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ValerionConfigEntry) -> bool:
    """Bring a config entry made by an older version up to date.

    Minor version 2 (v0.0.11): the navigation key buttons are enabled by
    default. Up to v0.0.10 Home Assistant created them disabled, so switch
    those on once; buttons the user disabled stay disabled. With the system
    option "Enable newly added entities" off, Home Assistant marks new
    entities as disabled by the integration too, so nothing is switched on.
    """
    if entry.version == 1 and entry.minor_version < 2:  # noqa: PLR2004
        # Same rule as ValerionCoordinator.device_id.
        device_id = entry.unique_id or entry.entry_id
        key_buttons = {f"{device_id}_button_{key}" for key in NAVIGATION_KEYS}

        def enable_key_button(entity: er.RegistryEntry) -> dict[str, None] | None:
            if (
                entity.unique_id in key_buttons
                and entity.disabled_by == er.RegistryEntryDisabler.INTEGRATION
            ):
                return {"disabled_by": None}
            return None

        if not entry.pref_disable_new_entities:
            await er.async_migrate_entries(hass, entry.entry_id, enable_key_button)
        hass.config_entries.async_update_entry(entry, minor_version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ValerionConfigEntry) -> bool:
    """Set up a projector from a config entry.

    Setup never blocks on the projector being awake: a projector in standby
    is a normal state, so the coordinator reports it instead of failing.
    """
    client = AwolLinkClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        security_code=entry.data.get(CONF_SECURITY_CODE),
    )
    coordinator = ValerionCoordinator(hass, entry, client, mac=configured_mac(entry))
    await coordinator.async_load_locks()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ValerionConfigEntry) -> bool:
    """Unload a config entry. Sessions are never held open, so nothing to close."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ValerionConfigEntry) -> None:
    """Delete the learned locks when the projector is removed."""
    await lock_store(hass, entry.entry_id).async_remove()
