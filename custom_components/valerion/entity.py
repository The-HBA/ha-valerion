"""Base entity for the Valerion integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import Connection, ValerionCoordinator

if TYPE_CHECKING:
    from .lib import Command


class ValerionEntity(CoordinatorEntity[ValerionCoordinator]):
    """Common device information and availability for all entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ValerionCoordinator, context: Command | None = None) -> None:
        """Initialize; ``context`` tells the coordinator which command this entity needs."""
        super().__init__(coordinator, context)
        self.device_id = coordinator.device_id
        self._attr_unique_id = self.device_id
        # No MAC "connection" on purpose: the Android TV integrations register
        # the same MAC, and Home Assistant would then try to merge the two
        # devices (or refuse with a connection collision). The MAC is only
        # used for Wake-on-LAN.
        # The coordinator corrects model, name and firmware in the device
        # registry later if the projector's identity arrives or changes.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer=MANUFACTURER,
            configuration_url=None,
            **coordinator.device_details(),
        )
        self.host: str = coordinator.config_entry.data[CONF_HOST]

    @property
    def available(self) -> bool:
        """Entities are only meaningful while the projector answers."""
        return (
            super().available
            and self.coordinator.data.connection == Connection.ANSWERING
            and self.coordinator.data.is_on
        )

    @property
    def _power_control_available(self) -> bool:
        """Availability for entities that switch the projector on.

        They stay available while off so ``turn_on`` can wake the projector.
        Only an unreachable projector without a known MAC address is truly
        unavailable, because then there is no way to switch it on. A projector
        that refuses the connection (AWOL Link off) cannot be controlled at all.
        """
        if not self.coordinator.last_update_success:
            return False
        data = self.coordinator.data
        if data.connection == Connection.REFUSED:
            return False
        return not (data.connection == Connection.UNREACHABLE and not self.coordinator.mac)
