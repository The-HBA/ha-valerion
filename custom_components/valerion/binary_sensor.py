"""Binary sensor entities for the Valerion integration.

The problem sensor turns on when the projector's LED status (``%3LEDS``)
reports anything other than normal: overtemperature, a fan error and so on.
The diagnostic *LED status* sensor names the exact problem.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .entity import ValerionEntity
from .lib import LedStatus, protocol

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import ValerionConfigEntry, ValerionCoordinator

# Binary sensors only read the coordinator's data; they never send commands.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValerionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors for a config entry."""
    async_add_entities([ValerionProblemSensor(entry.runtime_data)])


class ValerionProblemSensor(ValerionEntity, BinarySensorEntity):
    """On while the LED status is not normal. Named "Problem" after its device class."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ValerionCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, protocol.LED_STATUS)
        self._attr_unique_id = f"{self.device_id}_problem"

    @property
    def is_on(self) -> bool | None:
        """Return True for every status except normal, including undocumented codes."""
        raw = self.coordinator.data.value(protocol.LED_STATUS)
        return raw != LedStatus.NORMAL if raw is not None else None
