"""The Valerion integration: local control of Valerion projectors over AWOL Link."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    CONF_SECURITY_CODE,
    CONF_SHOW_PANEL,
    CONF_STATUS_NOTIFICATIONS,
    DOMAIN,
    NAVIGATION_KEYS,
)
from .coordinator import ValerionConfigEntry, ValerionCoordinator, configured_macs, lock_store
from .frontend import async_remove_frontend, async_setup_frontend, async_update_panel
from .lib import AwolLinkClient
from .notifications import async_start_notifications
from .scenes import ValerionScenes, scene_store
from .services import async_setup_services
from .websocket import async_register_commands

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.REMOTE,
    Platform.SCENE,
    Platform.SELECT,
    Platform.SENSOR,
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions once, independent of any projector being set up."""
    async_setup_services(hass)
    async_register_commands(hass)
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
    await async_setup_frontend(hass)
    client = AwolLinkClient(
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        security_code=entry.data.get(CONF_SECURITY_CODE),
    )
    coordinator = ValerionCoordinator(hass, entry, client, macs=configured_macs(entry))
    await coordinator.async_load_locks()
    coordinator.scenes = ValerionScenes(hass, coordinator)
    await coordinator.scenes.async_load()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if entry.options.get(CONF_STATUS_NOTIFICATIONS):
        await async_start_notifications(hass, entry)
    await async_update_panel(hass, entry.entry_id, show=entry.options.get(CONF_SHOW_PANEL, True))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ValerionConfigEntry) -> bool:
    """Unload a config entry. Sessions are never held open, so nothing to close.

    The sidebar page goes with the last loaded projector that shows it.
    """
    if unloaded := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await async_update_panel(hass, entry.entry_id, show=False)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ValerionConfigEntry) -> None:
    """Delete the learned locks and scenes, and the card resource with the last projector."""
    await lock_store(hass, entry.entry_id).async_remove()
    await scene_store(hass, entry.entry_id).async_remove()
    await async_remove_frontend(hass, entry)
