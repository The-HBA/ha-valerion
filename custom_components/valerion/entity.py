"""Base entity for the Valerion integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, NAME
from .coordinator import Connection, ValerionCoordinator

if TYPE_CHECKING:
    from .lib import Command


class ValerionEntity(CoordinatorEntity[ValerionCoordinator]):
    """Common device information and availability for all entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ValerionCoordinator, context: Command | None = None) -> None:
        """Initialize; ``context`` tells the coordinator which command this entity needs."""
        super().__init__(coordinator, context)
        entry = coordinator.config_entry
        self.device_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = self.device_id
        identity = coordinator.data.identity
        connections = {(CONNECTION_NETWORK_MAC, coordinator.mac)} if coordinator.mac else set()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            connections=connections,
            manufacturer=MANUFACTURER,
            model=identity.model or NAME,
            name=identity.name or entry.title,
            sw_version=identity.software_version,
            configuration_url=None,
        )
        self.host: str = entry.data[CONF_HOST]

    @property
    def available(self) -> bool:
        """Entities are only meaningful while the projector answers."""
        return (
            super().available
            and self.coordinator.data.connection == Connection.ANSWERING
            and self.coordinator.data.is_on
        )
