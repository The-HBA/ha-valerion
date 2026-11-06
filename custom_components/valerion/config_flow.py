"""Config flow for the Valerion integration."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
import logging
from typing import TYPE_CHECKING, Any, Final

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util.network import is_host_valid
import probatio

from .const import (
    CONF_MAC_ETHERNET,
    CONF_SECURITY_CODE,
    CONF_STATUS_NOTIFICATIONS,
    CONF_ZEROCONF_ID,
    DOMAIN,
    NAME,
)
from .coordinator import configured_mac
from .lib import (
    DEFAULT_PORT,
    AwolLinkAuthError,
    AwolLinkClient,
    AwolLinkCommandError,
    AwolLinkConnectionError,
    AwolLinkError,
    AwolLinkProtocolError,
    AwolLinkRefusedError,
    AwolLinkUnresponsiveError,
    discover,
    local_address_towards,
    normalize_mac,
    protocol,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

_LOGGER = logging.getLogger(__name__)

#: Name patterns (lower case, ``fnmatch`` style) of Android TV Remote
#: announcements that look like a Valerion projector. A VisionMaster Pro2
#: announces ``VisionMaster``. Every announcement is still checked on AWOL Link,
#: so a renamed projector is found; the name only decides whether a device that
#: refuses AWOL Link is suggested anyway, with the hint to switch AWOL Link on.
ZEROCONF_NAME_PATTERNS: Final[tuple[str, ...]] = (
    "visionmaster*",
    "streammaster*",
    "aetherion*",
    "*valerion*",
)
#: Discovered projectors are reached on the default AWOL Link port.
DISCOVERY_PORT: Final = DEFAULT_PORT
#: The AWOL Link check runs for every Android TV device on the network, so it is short.
PROBE_TIMEOUT: Final = 2.0
#: How long the network search waits for answers, in seconds.
SEARCH_SECONDS: Final = 3.0
#: A projector answers the search with ``%2ACKN=<network name>``.
SEARCH_REPLY: Final = "ACKN"
#: Value of the "enter the IP address manually" choice in the list of found projectors.
MANUAL_ENTRY: Final = "manual"
CONF_PROJECTOR: Final = "projector"

#: The security code field hides what is typed, like a password field.
CODE_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

STEP_USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Optional(probatio.Secret(CONF_SECURITY_CODE)): CODE_SELECTOR,
        probatio.Optional(CONF_MAC): str,
        probatio.Optional(CONF_MAC_ETHERNET): str,
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

SECURITY_CODE_SCHEMA = probatio.Schema(
    {probatio.Required(probatio.Secret(CONF_SECURITY_CODE)): CODE_SELECTOR}
)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_MAC): str,
        probatio.Optional(CONF_MAC_ETHERNET): str,
        probatio.Optional(CONF_STATUS_NOTIFICATIONS, default=False): bool,
    }
)


@dataclass(slots=True)
class _Projector:
    """A projector found by zeroconf or by the network search."""

    host: str
    #: Network name from the announcement or the search reply.
    name: str
    zeroconf_id: str | None = None
    #: True when the projector greets with a security code; None when not checked.
    needs_code: bool | None = None


class ValerionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI setup of a projector."""

    VERSION = 1
    #: 2 (v0.0.11): navigation key buttons enabled by default.
    MINOR_VERSION = 2

    _searched: bool = False
    _found: dict[str, _Projector]
    _projector: _Projector

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ValerionOptionsFlow:  # noqa: ARG004
        """Show the settings (gear) button for every projector."""
        return ValerionOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Search the network first, then ask for the connection details and test them."""
        if user_input is None and not self._searched:
            self._searched = True
            self._found = await self._async_search()
            if self._found:
                return await self.async_step_pick_projector()

        errors: dict[str, str] = {}
        if user_input is not None:
            host: str = user_input[CONF_HOST].strip()
            port: int = user_input[CONF_PORT]
            code = _code(user_input)
            macs = _macs(user_input, errors)

            if not is_host_valid(host):
                errors[CONF_HOST] = "invalid_host"

            if not errors and (title := await _async_try_connect(host, port, code, errors)):
                return await self._async_create(host, port, code, title, macs)

        return self._async_show_user_form(user_input, errors)

    async def async_step_pick_projector(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """List the projectors that answered the network search."""
        if user_input is not None:
            if (choice := user_input[CONF_PROJECTOR]) == MANUAL_ENTRY:
                return self._async_show_user_form(None, {})
            self._projector = self._found[choice]
            errors: dict[str, str] = {}
            if result := await self._async_connect_found(None, errors):
                return result
            if errors == {"base": "invalid_auth"}:
                return await self.async_step_security_code()
            # Show the address in the manual form, with the reason it failed.
            return self._async_show_user_form({CONF_HOST: choice}, errors)

        options = [
            SelectOptionDict(value=host, label=f"{found.name} ({host})")
            for host, found in self._found.items()
        ]
        options.append(SelectOptionDict(value=MANUAL_ENTRY, label=MANUAL_ENTRY))
        schema = probatio.Schema(
            {
                probatio.Required(CONF_PROJECTOR): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        translation_key=CONF_PROJECTOR,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="pick_projector", data_schema=schema)

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> ConfigFlowResult:
        """Check whether an Android TV Remote announcement is a Valerion with AWOL Link.

        Every Android TV device on the network comes through here, so the
        cheap checks run first and the AWOL Link check opens one short session.
        """
        addresses = [
            str(address)
            for address in (discovery_info.ip_address, *discovery_info.ip_addresses)
            if address.version == 4  # noqa: PLR2004
        ]
        if not addresses:
            return self.async_abort(reason="not_ipv4_address")
        name = discovery_info.name.removesuffix(f".{discovery_info.type}")
        if not (device_id := discovery_info.properties.get("bt")):
            return self.async_abort(reason="no_device_id")
        zeroconf_id = format_mac(str(device_id))

        await self.async_set_unique_id(zeroconf_id)
        await self._async_abort_known_projector(zeroconf_id, addresses)
        # Also aborts when the user chose to ignore this projector.
        self._abort_if_unique_id_configured()

        host = addresses[0]
        try:
            needs_code = await _async_check(host)
        except AwolLinkRefusedError:
            if not _looks_like_valerion(name):
                _LOGGER.debug("%s at %s refuses AWOL Link", name, host)
                return self.async_abort(reason="not_valerion")
            # Refusing the connection is what a Valerion does with AWOL Link off.
            self._projector = _Projector(host, name, zeroconf_id)
            self.context["title_placeholders"] = {"name": name}
            return await self.async_step_zeroconf_awol_link_off()
        except AwolLinkError, AwolLinkProtocolError:
            _LOGGER.debug("%s at %s does not answer on AWOL Link", name, host)
            return self.async_abort(reason="not_valerion")
        self._projector = _Projector(host, name, zeroconf_id, needs_code)
        self.context["title_placeholders"] = {"name": name}
        if not needs_code:
            self._set_confirm_only()
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_awol_link_off(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask to switch AWOL Link on for a projector found by its name, then check again."""
        errors: dict[str, str] = {}
        if user_input is not None:
            found = self._projector
            try:
                found.needs_code = await _async_check(found.host)
            except AwolLinkRefusedError:
                errors["base"] = "awol_link_off"
            except AwolLinkUnresponsiveError:
                errors["base"] = "projector_asleep"
            except AwolLinkError, AwolLinkProtocolError:
                errors["base"] = "cannot_connect"
            else:
                if found.needs_code:
                    return await self.async_step_security_code()
                if result := await self._async_connect_found(None, errors):
                    return result
                if errors == {"base": "invalid_auth"}:
                    return await self.async_step_security_code()
        return self.async_show_form(
            step_id="zeroconf_awol_link_off",
            description_placeholders=self._placeholders(),
            errors=errors,
        )

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask whether to add the projector that was found."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if self._projector.needs_code:
                return await self.async_step_security_code()
            if result := await self._async_connect_found(None, errors):
                return result
            if errors == {"base": "invalid_auth"}:
                return await self.async_step_security_code()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders=self._placeholders(),
            errors=errors,
        )

    async def async_step_security_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the security code of a projector that was found and needs one."""
        errors: dict[str, str] = {}
        if user_input is not None and (
            result := await self._async_connect_found(_code(user_input), errors)
        ):
            return result
        return self.async_show_form(
            step_id="security_code",
            data_schema=SECURITY_CODE_SCHEMA,
            description_placeholders=self._placeholders(),
            errors=errors,
        )

    @callback
    def _async_show_user_form(
        self, user_input: Mapping[str, Any] | None, errors: dict[str, str]
    ) -> ConfigFlowResult:
        """Show the form for the IP address, port, security code and MAC addresses."""
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(STEP_USER_SCHEMA, user_input),
            errors=errors,
        )

    @callback
    def _placeholders(self) -> dict[str, str]:
        return {"name": self._projector.name, "host": self._projector.host}

    async def _async_search(self) -> dict[str, _Projector]:
        """Send the AWOL Link search; return the projectors not set up yet, by host."""
        try:
            replies = await discover(wait=SEARCH_SECONDS)
        except OSError as err:
            _LOGGER.debug("Network search failed: %s", err)
            return {}
        configured = {
            entry.data.get(CONF_HOST) for entry in self._async_current_entries(include_ignore=False)
        }
        found: dict[str, _Projector] = {}
        for reply in replies:
            if reply.code == SEARCH_REPLY and reply.host not in configured:
                found.setdefault(reply.host, _Projector(reply.host, reply.value.strip() or NAME))
        return found

    async def _async_abort_known_projector(self, zeroconf_id: str, addresses: list[str]) -> None:
        """Abort for a projector already set up, and follow a changed IP address.

        A projector set up by hand has a Wi-Fi or Ethernet MAC as unique ID, or
        none, so it is recognised by its address first. Its device ID is stored
        then, so a later announcement from a new address is still recognised.
        The ID is only stored when AWOL Link answers there: another device may
        now use an address the projector had before.
        """
        entries = self._async_current_entries(include_ignore=False)
        for entry in entries:
            if zeroconf_id in (entry.unique_id, entry.data.get(CONF_ZEROCONF_ID)):
                # An announcement can list addresses of other devices too: keep a
                # stored address that is still in the list.
                if entry.data.get(CONF_HOST) not in addresses:
                    changed = self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, CONF_HOST: addresses[0]}
                    )
                    if changed and entry.state in (
                        ConfigEntryState.LOADED,
                        ConfigEntryState.SETUP_RETRY,
                    ):
                        self.hass.config_entries.async_schedule_reload(entry.entry_id)
                raise AbortFlow("already_configured")
        for entry in entries:
            if (host := entry.data.get(CONF_HOST)) in addresses:
                if await _async_probe(host) is not None:
                    self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, CONF_ZEROCONF_ID: zeroconf_id}
                    )
                raise AbortFlow("already_configured")

    async def _async_connect_found(
        self, code: str | None, errors: dict[str, str]
    ) -> ConfigFlowResult | None:
        """Test a found projector like the manual step; None with the reason in ``errors``."""
        found = self._projector
        title = await _async_try_connect(found.host, DISCOVERY_PORT, code, errors, found.name)
        if title is None:
            return None
        extra = {CONF_ZEROCONF_ID: found.zeroconf_id} if found.zeroconf_id else {}
        return await self._async_create(found.host, DISCOVERY_PORT, code, title, extra)

    async def _async_create(
        self, host: str, port: int, code: str | None, title: str, extra: Mapping[str, str]
    ) -> ConfigFlowResult:
        """Create the entry, unless this projector is already set up.

        ``extra`` holds the MAC addresses typed in the manual step (empty when
        left empty) or the zeroconf device ID. The first MAC is the unique ID.
        """
        if unique_id := extra.get(CONF_MAC) or extra.get(CONF_MAC_ETHERNET):
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})
        # Also catches a projector first set up without a MAC.
        self._async_abort_entries_match({CONF_HOST: host})
        data = _connection_data(host, port, code)
        data.update({key: value for key, value in extra.items() if value})
        return self.async_create_entry(title=title, data=data)

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
        addresses are changed with the settings (gear) button instead.
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

    The MAC addresses live here so they can be added later. They are only used
    for Wake-on-LAN: the device and entity IDs never change with them. Instant
    updates are off by default, because they also need a setting on the projector.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the MAC addresses (empty removes one) and instant updates."""
        errors: dict[str, str] = {}
        if user_input is not None:
            macs = _macs(user_input, errors)
            if not errors:
                # Always store both keys: an empty value overrides a MAC that
                # was entered during the first setup.
                return self.async_create_entry(
                    data={
                        **self.config_entry.options,
                        **macs,
                        CONF_STATUS_NOTIFICATIONS: user_input[CONF_STATUS_NOTIFICATIONS],
                    }
                )
        suggested = user_input or {
            key: configured_mac(self.config_entry, key) or ""
            for key in (CONF_MAC, CONF_MAC_ETHERNET)
        } | {
            CONF_STATUS_NOTIFICATIONS: self.config_entry.options.get(
                CONF_STATUS_NOTIFICATIONS, False
            )
        }
        address = await self.hass.async_add_executor_job(
            local_address_towards, self.config_entry.data[CONF_HOST]
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, suggested),
            description_placeholders={"address": address or "Home Assistant's IP address"},
            errors=errors,
        )


def _macs(user_input: Mapping[str, Any], errors: dict[str, str]) -> dict[str, str]:
    """Return the Wi-Fi and Ethernet MAC addresses, empty when a field was left empty."""
    macs: dict[str, str] = {}
    for key in (CONF_MAC, CONF_MAC_ETHERNET):
        macs[key] = (user_input.get(key) or "").strip()
        if macs[key]:
            try:
                macs[key] = format_mac(normalize_mac(macs[key]))
            except ValueError:
                errors[key] = "invalid_mac"
    return macs


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
    host: str, port: int, code: str | None, errors: dict[str, str], found_name: str | None = None
) -> str | None:
    """Test the connection; return a title, or None with the reason in ``errors``.

    ``found_name`` is the network name from discovery, used as the title when
    the projector does not tell its name over AWOL Link.
    """
    try:
        return await _async_validate(host, port, code, found_name)
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


async def _async_validate(
    host: str, port: int, code: str | None, found_name: str | None = None
) -> str:
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
    for candidate in (name, found_name, model):
        if candidate and candidate.strip():
            return candidate.strip()
    return NAME


async def _async_probe(host: str) -> bool | None:
    """Check that AWOL Link answers; return whether a security code is needed.

    Returns None when nothing answers like AWOL Link on the default port.
    """
    try:
        return await _async_check(host)
    except AwolLinkError, AwolLinkProtocolError:
        return None


async def _async_check(host: str) -> bool:
    """Open one short session without a code; return whether a security code is needed.

    Raises :class:`AwolLinkRefusedError` when the device refuses the
    connection (a Valerion does that with AWOL Link off), another
    :class:`AwolLinkError` or :class:`AwolLinkProtocolError` when nothing
    answers like AWOL Link.
    """
    client = AwolLinkClient(host, DISCOVERY_PORT, timeout=PROBE_TIMEOUT)
    try:
        await client.probe()
    except AwolLinkAuthError:
        return True
    return False


def _looks_like_valerion(name: str) -> bool:
    """Whether an announced name matches one of :data:`ZEROCONF_NAME_PATTERNS`."""
    return any(fnmatch(name.lower(), pattern) for pattern in ZEROCONF_NAME_PATTERNS)
