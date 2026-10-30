"""Config flow for the Valerion integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.util.network import is_host_valid
import probatio

from .const import CONF_SECURITY_CODE, DOMAIN, NAME
from .coordinator import configured_mac
from .lib import (
    DEFAULT_PORT,
    AwolLinkAuthError,
    AwolLinkClient,
    AwolLinkCommandError,
    AwolLinkConnectionError,
    AwolLinkRefusedError,
    AwolLinkUnresponsiveError,
    normalize_mac,
    protocol,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Optional(probatio.Secret(CONF_SECURITY_CODE)): str,
        probatio.Optional(CONF_MAC): str,
    }
)

OPTIONS_SCHEMA = probatio.Schema({probatio.Optional(CONF_MAC): str})


class ValerionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup of a projector."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ValerionOptionsFlow:  # noqa: ARG004
        """Show the settings (gear) button for every projector."""
        return ValerionOptionsFlow()

    async def async_step_user(  # noqa: C901, PLR0912
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the connection details and test them against the projector."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host: str = user_input[CONF_HOST].strip()
            port: int = user_input[CONF_PORT]
            code: str | None = (user_input.get(CONF_SECURITY_CODE) or "").strip() or None
            mac_input: str = (user_input.get(CONF_MAC) or "").strip()
            mac: str | None = None

            if not is_host_valid(host):
                errors[CONF_HOST] = "invalid_host"
            if mac_input:
                try:
                    mac = format_mac(normalize_mac(mac_input))
                except ValueError:
                    errors[CONF_MAC] = "invalid_mac"

            if not errors:
                try:
                    title = await _async_validate(host, port, code)
                except AwolLinkUnresponsiveError:
                    errors["base"] = "projector_asleep"
                except AwolLinkAuthError:
                    errors["base"] = "invalid_auth"
                except AwolLinkRefusedError:
                    errors["base"] = "awol_link_off"
                except AwolLinkConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error while validating %s", host)
                    errors["base"] = "unknown"
                else:
                    if mac:
                        await self.async_set_unique_id(mac)
                        self._abort_if_unique_id_configured(
                            updates={CONF_HOST: host, CONF_PORT: port}
                        )
                    # Also catches a projector first set up without a MAC.
                    self._async_abort_entries_match({CONF_HOST: host})
                    data = {CONF_HOST: host, CONF_PORT: port}
                    if code:
                        data[CONF_SECURITY_CODE] = code
                    if mac:
                        data[CONF_MAC] = mac
                    return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, user_input),
            errors=errors,
        )


class ValerionOptionsFlow(OptionsFlowWithReload):
    """Settings that can change after setup; saving reloads the projector.

    The MAC address lives here so it can be added later. It is only used for
    Wake-on-LAN: the device and entity IDs never change with it.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the MAC address (empty removes it)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            mac_input: str = (user_input.get(CONF_MAC) or "").strip()
            mac = ""
            if mac_input:
                try:
                    mac = format_mac(normalize_mac(mac_input))
                except ValueError:
                    errors[CONF_MAC] = "invalid_mac"
            if not errors:
                # Always store the key: an empty value overrides a MAC that
                # was entered during the first setup.
                return self.async_create_entry(data={**self.config_entry.options, CONF_MAC: mac})
        suggested = user_input or {CONF_MAC: configured_mac(self.config_entry) or ""}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, suggested),
            errors=errors,
        )


async def _async_validate(host: str, port: int, code: str | None) -> str:
    """Open one session, read the identity and return a title for the entry."""
    client = AwolLinkClient(host, port, security_code=code)
    async with client.session() as session:
        model: str | None = None
        name: str | None = None
        try:
            model = await session.query(protocol.MODEL)
        except AwolLinkCommandError:
            model = None
        try:
            name = await session.query(protocol.NAME)
        except AwolLinkCommandError:
            name = None
    for candidate in (name, model):
        if candidate and candidate.strip():
            return candidate.strip()
    return NAME
