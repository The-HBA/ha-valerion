"""Remote entity for the Valerion integration.

Sends the documented AWOL Link key presses (navigation keys, volume steps and
the lens menus) by name through ``remote.send_command``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
)
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .entity import ValerionEntity
from .lib import KEYS, key_press

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import ValerionConfigEntry, ValerionCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValerionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the remote for a config entry."""
    async_add_entities([ValerionRemote(entry.runtime_data)])


class ValerionRemote(ValerionEntity, RemoteEntity):
    """The projector's remote control keys."""

    _attr_translation_key = "remote"

    def __init__(self, coordinator: ValerionCoordinator) -> None:
        """Initialize the remote."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device_id}_remote"

    @property
    def available(self) -> bool:
        """Stay available while off so ``turn_on`` can wake the projector."""
        return self._power_control_available

    @property
    def is_on(self) -> bool:
        """Return True while the projector is on."""
        return self.coordinator.data.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:  # noqa: ARG002 - HA API
        """Wake the projector (Wake-on-LAN) and switch it on."""
        await self.coordinator.async_power_on()

    async def async_turn_off(self, **kwargs: Any) -> None:  # noqa: ARG002 - HA API
        """Put the projector in standby, or fully off if configured so."""
        await self.coordinator.async_power_off()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send key presses by name, for example ``["down", "down", "ok"]``."""
        names = list(command)
        try:
            presses = [key_press(name) for name in names]
        except KeyError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_key",
                translation_placeholders={"key": str(err.args[0]), "keys": ", ".join(KEYS)},
            ) from err
        if not self.coordinator.data.is_on:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="projector_off")

        repeats = int(kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS))
        delay = float(kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS))
        await self.coordinator.async_press_keys(presses * repeats, delay=delay)
        await self.coordinator.async_request_refresh()
