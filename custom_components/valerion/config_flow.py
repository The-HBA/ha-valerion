"""Config flow for the Valerion integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType
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

if TYPE_CHECKING:
    from collections.abc import Mapping

_LOGGER = logging.getLogger(__name__)

#: The security code field hides what is typed, like a password field.
CODE_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

STEP_USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Optional(probatio.Secret(CONF_SECURITY_CODE)): CODE_SELECTOR,
        probatio.Optional(CONF_MAC): str,
    }
)

RECONFIGURE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Optional(probatio.Secret(CONF_SECURITY_CODE)): CODE_SELECTOR,
    }
)

REAUTH_SCHEMA = probatio.Schema(
    {probatio.Optional(probatio.Secret(CONF_SECURITY_CODE)): CODE_SELECTOR}
)

OPTIONS_SCHEMA = probatio.Schema({probatio.Optional(CONF_MAC): str})


class ValerionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup of a projector."""

    VERSION = 1
    #: 2 (v0.0.11): navigation key buttons enabled by default.
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ValerionOptionsFlow:  # noqa: ARG004
        """Show the settings (gear) button for every projector."""
        return ValerionOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the connection details and test them against the projector."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host: str = user_input[CONF_HOST].strip()
            port: int = user_input[CONF_PORT]
            code = _code(user_input)
            mac_input: str = (user_input.get(CONF_MAC) or "").strip()
            mac: str | None = None

            if not is_host_valid(host):
                errors[CONF_HOST] = "invalid_host"
            if mac_input:
                try:
                    mac = format_mac(normalize_mac(mac_input))
                except ValueError:
                    errors[CONF_MAC] = "invalid_mac"

            if not errors and (title := await _async_try_connect(host, port, code, errors)):
                if mac:
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})
                # Also catches a projector first set up without a MAC.
                self._async_abort_entries_match({CONF_HOST: host})
                data = _connection_data(host, port, code)
                if mac:
                    data[CONF_MAC] = mac
                return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:  # noqa: ARG002
        """Start when the projector refuses the stored security code, or asks for one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the security code that is now set on the projector."""
        entry = self._get_reauth_entry()
        host: str = entry.data[CONF_HOST]
        port: int = entry.data[CONF_PORT]
        errors: dict[str, str] = {}
        if user_input is not None:
            code = _code(user_input)
            if await _async_try_connect(host, port, code, errors):
                return self.async_update_reload_and_abort(
                    entry, data=_with_connection(entry.data, host, port, code)
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"name": entry.title, "host": host},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the IP address, port or security code of a projector already set up.

        The device, its entities and their history stay as they are. The MAC
        address is changed with the settings (gear) button instead.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host: str = user_input[CONF_HOST].strip()
            port: int = user_input[CONF_PORT]
            code = _code(user_input)
            if not is_host_valid(host):
                errors[CONF_HOST] = "invalid_host"
            elif any(
                other.data.get(CONF_HOST) == host
                for other in self._async_current_entries(include_ignore=False)
                if other.entry_id != entry.entry_id
            ):
                return self.async_abort(reason="already_configured")
            elif await _async_try_connect(host, port, code, errors):
                return self.async_update_reload_and_abort(
                    entry, data=_with_connection(entry.data, host, port, code)
                )
        suggested = user_input or {
            CONF_HOST: entry.data[CONF_HOST],
            CONF_PORT: entry.data[CONF_PORT],
            CONF_SECURITY_CODE: entry.data.get(CONF_SECURITY_CODE, ""),
        }
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(RECONFIGURE_SCHEMA, suggested),
            description_placeholders={"name": entry.title},
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


def _code(user_input: Mapping[str, Any]) -> str | None:
    """Return the typed security code, or None when the field was left empty."""
    return (user_input.get(CONF_SECURITY_CODE) or "").strip() or None


def _connection_data(host: str, port: int, code: str | None) -> dict[str, Any]:
    """Return the entry data for one connection; without a code there is no code key."""
    data: dict[str, Any] = {CONF_HOST: host, CONF_PORT: port}
    if code:
        data[CONF_SECURITY_CODE] = code
    return data


def _with_connection(
    data: Mapping[str, Any], host: str, port: int, code: str | None
) -> dict[str, Any]:
    """Return ``data`` with new connection details; other keys (the MAC) stay."""
    kept = {
        key: value
        for key, value in data.items()
        if key not in (CONF_HOST, CONF_PORT, CONF_SECURITY_CODE)
    }
    return {**kept, **_connection_data(host, port, code)}


async def _async_try_connect(
    host: str, port: int, code: str | None, errors: dict[str, str]
) -> str | None:
    """Test the connection; return a title, or None with the reason in ``errors``."""
    try:
        return await _async_validate(host, port, code)
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
    return None


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
