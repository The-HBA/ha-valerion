"""Actions (services) for the Valerion integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import selector, service
import probatio

from .const import DOMAIN
from .lib import AwolLinkProtocolError, parse_command_line

if TYPE_CHECKING:
    from homeassistant.core import ServiceResponse

    from .coordinator import ValerionConfigEntry

ATTR_CONFIG_ENTRY: Final = "config_entry"
ATTR_COMMAND: Final = "command"

SERVICE_SEND_RAW_COMMAND: Final = "send_raw_command"
SERVICE_SEND_RAW_COMMAND_SCHEMA: Final = probatio.Schema(
    {
        probatio.Optional(ATTR_CONFIG_ENTRY): selector.ConfigEntrySelector({"integration": DOMAIN}),
        probatio.Required(ATTR_COMMAND): str,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions."""

    async def send_raw_command(call: ServiceCall) -> ServiceResponse:
        """Send one AWOL Link line and return the projector's reply."""
        # Without a config entry this picks the only configured projector.
        entry: ValerionConfigEntry = service.async_get_config_entry(
            call.hass, DOMAIN, call.data.get(ATTR_CONFIG_ENTRY)
        )
        try:
            command, value = parse_command_line(call.data[ATTR_COMMAND])
        except AwolLinkProtocolError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_raw_command",
                translation_placeholders={"command": call.data[ATTR_COMMAND]},
            ) from err
        coordinator = entry.runtime_data
        reply = await coordinator.async_send_raw(command, value)
        await coordinator.async_request_refresh()
        return {"command": command.set(value), "reply": reply}

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_RAW_COMMAND,
        send_raw_command,
        schema=SERVICE_SEND_RAW_COMMAND_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
