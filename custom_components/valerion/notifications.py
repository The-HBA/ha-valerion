"""Optional instant updates from the projector's Status Notification messages.

All projectors share one UDP port on this machine, so one hub owns the socket
and passes each message to the projector it came from. A message only starts
an early poll: it has no authentication, so what the poll reads is what counts.
Polling carries on as usual, and is all that is left if the messages stop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .lib import NOTIFICATION_PORT, listen_for_notifications, resolve_ipv4

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import ValerionConfigEntry, ValerionCoordinator
    from .lib import Response

_LOGGER = logging.getLogger(__name__)

_HUB: HassKey[_NotificationHub] = HassKey(f"{DOMAIN}_notifications")
ISSUE_PORT_UNAVAILABLE = "notification_port_unavailable"


class _NotificationHub:
    """Owns the socket for as long as a projector wants the messages."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._by_address: dict[str, ValerionCoordinator] = {}
        self._transport: asyncio.DatagramTransport | None = None
        #: Projectors set up side by side must not both try to open the port.
        self._opening = asyncio.Lock()

    async def async_add(self, addresses: set[str], coordinator: ValerionCoordinator) -> None:
        """Pass messages from ``addresses`` to ``coordinator``, opening the port if needed."""
        self._by_address.update(dict.fromkeys(addresses, coordinator))
        async with self._opening:
            if self._transport is None:
                await self._async_open()
        coordinator.notifications_listening = self._transport is not None

    async def _async_open(self) -> None:
        try:
            self._transport = await listen_for_notifications(self._received, port=NOTIFICATION_PORT)
        except OSError as err:
            _LOGGER.warning(
                "Cannot listen for Status Notification on UDP port %s: %s. "
                "The projector is still polled",
                NOTIFICATION_PORT,
                err,
            )
            ir.async_create_issue(
                self._hass,
                DOMAIN,
                ISSUE_PORT_UNAVAILABLE,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_PORT_UNAVAILABLE,
                translation_placeholders={"port": str(NOTIFICATION_PORT)},
            )
            return
        ir.async_delete_issue(self._hass, DOMAIN, ISSUE_PORT_UNAVAILABLE)

    @callback
    def async_remove(self, coordinator: ValerionCoordinator) -> None:
        """Stop passing messages to ``coordinator``; the last one closes the port."""
        self._by_address = {
            address: other
            for address, other in self._by_address.items()
            if other is not coordinator
        }
        if self._by_address:
            return
        ir.async_delete_issue(self._hass, DOMAIN, ISSUE_PORT_UNAVAILABLE)
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    @callback
    def _received(self, sender: str, message: Response) -> None:
        coordinator = self._by_address.get(sender)
        if coordinator is None:
            _LOGGER.debug("Ignoring %s from %s, not a configured projector", message.header, sender)
            return
        coordinator.async_notification_received(message)


async def async_start_notifications(hass: HomeAssistant, entry: ValerionConfigEntry) -> None:
    """Listen for this projector's messages until the entry is unloaded."""
    coordinator = entry.runtime_data
    host = entry.data[CONF_HOST]
    addresses = await resolve_ipv4(host)
    if not addresses:
        # Status Notification sends from an IPv4 address, and the sender is
        # how a message is matched to its projector.
        _LOGGER.warning("Cannot use Status Notification: no IPv4 address found for %s", host)
        return
    hub = hass.data.setdefault(_HUB, _NotificationHub(hass))
    await hub.async_add(addresses, coordinator)

    @callback
    def stop() -> None:
        hub.async_remove(coordinator)

    entry.async_on_unload(stop)
