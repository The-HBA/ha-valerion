"""Sensor entities for the Valerion integration.

The AWOL Link status sensor records how the projector answered the last poll
(answering, silent, refused, unreachable). Together with the media player's
on / standby / off state, Home Assistant history then shows how deep the
projector sleeps in standby.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory

from .coordinator import Connection, ValerionConfigEntry, ValerionCoordinator
from .entity import ValerionEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

# Sensors only read the coordinator's data; they never send commands.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValerionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors for a config entry."""
    async_add_entities([ValerionLinkStatusSensor(entry.runtime_data)])


class ValerionLinkStatusSensor(ValerionEntity, SensorEntity):
    """How the projector answered the last AWOL Link poll."""

    _attr_translation_key = "link_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ValerionCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device_id}_link_status"
        self._attr_options = [state.value for state in Connection]

    @property
    def available(self) -> bool:
        """Stay available in every state; recording silence is the point."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> str:
        """Return the connection state of the last poll."""
        return self.coordinator.data.connection.value
