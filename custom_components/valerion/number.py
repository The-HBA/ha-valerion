"""Number entities for the Valerion integration: the laser brightness level."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberMode

from .entity import ValerionEntity
from .lib import LASER_LEVEL_MAX, LASER_LEVEL_MIN, protocol

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import ValerionConfigEntry, ValerionCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValerionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the numbers for a config entry."""
    async_add_entities([ValerionLaserLevel(entry.runtime_data)])


class ValerionLaserLevel(ValerionEntity, NumberEntity):
    """Laser brightness level, 0 to 10."""

    _attr_translation_key = "laser_level"
    _attr_native_min_value = LASER_LEVEL_MIN
    _attr_native_max_value = LASER_LEVEL_MAX
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: ValerionCoordinator) -> None:
        """Initialize the number."""
        super().__init__(coordinator, protocol.LASER_LEVEL)
        self._attr_unique_id = f"{self.device_id}_laser_level"

    @property
    def available(self) -> bool:
        """Unavailable while the projector reports the level as locked (ERR3)."""
        return (
            super().available and protocol.LASER_LEVEL.code not in self.coordinator.data.unavailable
        )

    @property
    def native_value(self) -> int | None:
        """Return the current level."""
        raw = self.coordinator.data.value(protocol.LASER_LEVEL)
        try:
            return int(raw) if raw is not None else None
        except ValueError:
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set a new level."""
        await self.coordinator.async_send(protocol.LASER_LEVEL, round(value))
