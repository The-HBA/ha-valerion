"""The Valerion integration: local control of Valerion projectors over AWOL Link."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT, Platform
from homeassistant.helpers import config_validation as cv

from .const import CONF_SECURITY_CODE, DOMAIN
from .coordinator import ValerionConfigEntry, ValerionCoordinator, lock_store
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
    coordinator = ValerionCoordinator(hass, entry, client, mac=entry.data.get(CONF_MAC))
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
