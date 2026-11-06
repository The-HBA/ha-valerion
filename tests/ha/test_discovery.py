"""Tests for automatic discovery (zeroconf) and the network search in the setup dialog."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from ipaddress import ip_address
import socket
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import (
    SOURCE_IGNORE,
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigEntryState,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.valerion.config_flow import CONF_PROJECTOR, MANUAL_ENTRY
from custom_components.valerion.const import CONF_SECURITY_CODE, CONF_ZEROCONF_ID, DOMAIN
from custom_components.valerion.lib import (
    AwolLinkAuthError,
    AwolLinkUnresponsiveError,
    DiscoveredDevice,
)
from tests.lib.fake_projector import DEFAULT_VALUES, FakeProjector

from .conftest import PROJECTOR_MAC

ANDROID_TV_TYPE = "_androidtvremote2._tcp.local."
ANNOUNCED_NAME = "VisionMaster Pro2 x GoogleTV2891"
#: The ``bt`` property as an Android TV device announces it (upper case).
DEVICE_ID = "00:00:5E:00:53:0A"
ZEROCONF_ID = "00:00:5e:00:53:0a"
OTHER_HOST = "192.0.2.20"


@pytest.fixture
def mock_setup_entry() -> Iterator[AsyncMock]:
    """Skip setting up the projector after the flow creates the entry."""
    with patch("custom_components.valerion.async_setup_entry", return_value=True) as mock:
        yield mock


@pytest.fixture
def at_port(projector: FakeProjector) -> Iterator[None]:
    """Let discovered projectors be reached on the fake projector's port."""
    with patch("custom_components.valerion.config_flow.DISCOVERY_PORT", projector.port):
        yield


def _announcement(
    *addresses: str, name: str = ANNOUNCED_NAME, device_id: str | None = DEVICE_ID
) -> ZeroconfServiceInfo:
    ips = [ip_address(address) for address in addresses or ("127.0.0.1",)]
    return ZeroconfServiceInfo(
        ip_address=ips[0],
        ip_addresses=ips,
        port=6466,
        hostname="android.local.",
        type=ANDROID_TV_TYPE,
        name=f"{name}.{ANDROID_TV_TYPE}",
        properties={"bt": device_id} if device_id else {},
    )


async def _discover(hass: HomeAssistant, info: ZeroconfServiceInfo) -> dict:
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=info
    )


def _entry(**kwargs: object) -> MockConfigEntry:
    data = kwargs.pop("data", {CONF_HOST: OTHER_HOST, CONF_PORT: 4352})
    return MockConfigEntry(domain=DOMAIN, data=data, version=1, minor_version=2, **kwargs)


async def test_zeroconf_finds_projector(
    hass: HomeAssistant, projector: FakeProjector, at_port: None, mock_setup_entry: AsyncMock
) -> None:
    result = await _discover(hass, _announcement())
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"] == {"name": ANNOUNCED_NAME, "host": "127.0.0.1"}
    (flow,) = hass.config_entries.flow.async_progress()
    assert flow["context"]["title_placeholders"] == {"name": ANNOUNCED_NAME}
    assert flow["context"]["confirm_only"] is True
    # The check opened one session and closed it again.
    assert projector.connections == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: projector.port,
        CONF_ZEROCONF_ID: ZEROCONF_ID,
    }
    assert result["result"].unique_id == ZEROCONF_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_takes_the_ipv4_address(
    hass: HomeAssistant, projector: FakeProjector, at_port: None
) -> None:
    result = await _discover(hass, _announcement("2001:db8::1", "127.0.0.1"))
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"]["host"] == "127.0.0.1"


async def test_zeroconf_ipv6_only_aborts(hass: HomeAssistant) -> None:
    result = await _discover(hass, _announcement("2001:db8::1"))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_ipv4_address"


async def test_zeroconf_without_device_id_aborts(hass: HomeAssistant) -> None:
    result = await _discover(hass, _announcement(device_id=None))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_device_id"


async def test_zeroconf_other_android_tv_aborts_quietly(
    hass: HomeAssistant, socket_enabled: None
) -> None:
    # Nothing listens on this port: an Android TV without AWOL Link refuses it.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]
    with patch("custom_components.valerion.config_flow.DISCOVERY_PORT", closed_port):
        result = await _discover(hass, _announcement(name="Living room TV"))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_valerion"


async def test_zeroconf_device_with_other_greeting_aborts(
    hass: HomeAssistant, socket_enabled: None
) -> None:
    async def greet(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(b"HELLO\r")
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(greet, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        with patch("custom_components.valerion.config_flow.DISCOVERY_PORT", port):
            result = await _discover(hass, _announcement())
    finally:
        server.close()
        await server.wait_closed()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_valerion"


@pytest.mark.parametrize(
    ("patterns", "step"),
    [(("aetherion*",), None), (("aetherion*", "visionmaster*"), "zeroconf_confirm")],
)
async def test_zeroconf_name_filter(
    hass: HomeAssistant,
    projector: FakeProjector,
    at_port: None,
    patterns: tuple[str, ...],
    step: str | None,
) -> None:
    with patch("custom_components.valerion.config_flow.ZEROCONF_NAME_PATTERNS", patterns):
        result = await _discover(hass, _announcement())
    if step is None:
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "not_valerion"
        # A name that does not match is never checked on AWOL Link.
        assert projector.connections == 0
    else:
        assert result["step_id"] == step


async def test_zeroconf_known_projector_follows_new_address(hass: HomeAssistant) -> None:
    entry = _entry(unique_id=ZEROCONF_ID, data={CONF_HOST: OTHER_HOST, CONF_PORT: 4352})
    entry.add_to_hass(hass)
    result = await _discover(hass, _announcement("192.0.2.30"))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_HOST: "192.0.2.30", CONF_PORT: 4352}


async def test_zeroconf_new_address_reloads_a_loaded_projector(hass: HomeAssistant) -> None:
    entry = _entry(unique_id=ZEROCONF_ID, state=ConfigEntryState.LOADED)
    entry.add_to_hass(hass)
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await _discover(hass, _announcement("192.0.2.30"))
    assert result["reason"] == "already_configured"
    reload.assert_called_once_with(entry.entry_id)


async def test_zeroconf_keeps_a_stored_address_still_announced(hass: HomeAssistant) -> None:
    entry = _entry(unique_id=ZEROCONF_ID)
    entry.add_to_hass(hass)
    result = await _discover(hass, _announcement("192.0.2.30", OTHER_HOST))
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == OTHER_HOST


async def test_zeroconf_learns_projector_set_up_by_hand(
    hass: HomeAssistant, projector: FakeProjector, at_port: None
) -> None:
    # Set up by hand with its Wi-Fi MAC: the address matches, the ID is stored.
    entry = _entry(
        unique_id=PROJECTOR_MAC,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: projector.port, CONF_MAC: PROJECTOR_MAC},
    )
    entry.add_to_hass(hass)
    result = await _discover(hass, _announcement())
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_ZEROCONF_ID] == ZEROCONF_ID
    assert entry.unique_id == PROJECTOR_MAC
    assert projector.connections == 1

    # Later the projector gets a new address and is still recognised.
    result = await _discover(hass, _announcement("192.0.2.30"))
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.0.2.30"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert projector.connections == 1


async def test_zeroconf_other_device_on_an_old_address(
    hass: HomeAssistant, socket_enabled: None
) -> None:
    # An Android TV now uses the address stored for the projector.
    entry = _entry(data={CONF_HOST: "127.0.0.1", CONF_PORT: 4352})
    entry.add_to_hass(hass)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]
    with patch("custom_components.valerion.config_flow.DISCOVERY_PORT", closed_port):
        result = await _discover(hass, _announcement(name="Living room TV"))
    assert result["reason"] == "already_configured"
    # Its device ID is not taken for the projector's.
    assert CONF_ZEROCONF_ID not in entry.data


async def test_zeroconf_ignored_projector_aborts(hass: HomeAssistant) -> None:
    _entry(unique_id=ZEROCONF_ID, source=SOURCE_IGNORE, data={}).add_to_hass(hass)
    result = await _discover(hass, _announcement())
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_asks_for_security_code(
    hass: HomeAssistant, socket_enabled: None, mock_setup_entry: AsyncMock
) -> None:
    fake = FakeProjector(security_code="1234", values=dict(DEFAULT_VALUES))
    await fake.start()
    try:
        with patch("custom_components.valerion.config_flow.DISCOVERY_PORT", fake.port):
            result = await _discover(hass, _announcement())
            assert result["step_id"] == "zeroconf_confirm"
            flow_id = result["flow_id"]
            (flow,) = hass.config_entries.flow.async_progress()
            assert "confirm_only" not in flow["context"]

            result = await hass.config_entries.flow.async_configure(flow_id, {})
            assert result["type"] is FlowResultType.FORM
            assert result["step_id"] == "security_code"
            assert result["description_placeholders"] == {
                "name": ANNOUNCED_NAME,
                "host": "127.0.0.1",
            }

            result = await hass.config_entries.flow.async_configure(
                flow_id, {CONF_SECURITY_CODE: "9999"}
            )
            assert result["step_id"] == "security_code"
            assert result["errors"] == {"base": "invalid_auth"}

            result = await hass.config_entries.flow.async_configure(
                flow_id, {CONF_SECURITY_CODE: " 1234 "}
            )
    finally:
        await fake.stop()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SECURITY_CODE] == "1234"
    assert result["data"][CONF_ZEROCONF_ID] == ZEROCONF_ID


async def test_zeroconf_confirm_errors(
    hass: HomeAssistant, projector: FakeProjector, at_port: None
) -> None:
    result = await _discover(hass, _announcement())
    flow_id = result["flow_id"]
    validate = "custom_components.valerion.config_flow._async_validate"
    # The projector went to sleep between the announcement and the click.
    with patch(validate, side_effect=AwolLinkUnresponsiveError("silent")):
        result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["step_id"] == "zeroconf_confirm"
    assert result["errors"] == {"base": "projector_asleep"}

    # A security code was set in the meantime.
    with patch(validate, side_effect=AwolLinkAuthError("code")):
        result = await hass.config_entries.flow.async_configure(flow_id, {})
    assert result["step_id"] == "security_code"


async def test_zeroconf_confirm_aborts_when_set_up_meanwhile(
    hass: HomeAssistant, projector: FakeProjector, at_port: None
) -> None:
    result = await _discover(hass, _announcement())
    _entry(data={CONF_HOST: "127.0.0.1", CONF_PORT: projector.port}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _reply(host: str, name: str, code: str = "ACKN") -> DiscoveredDevice:
    return DiscoveredDevice(host=host, raw=f"%2{code}={name}", code=code, value=name)


async def _search(hass: HomeAssistant) -> dict:
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})


def _choices(result: dict) -> list[tuple[str, str]]:
    selector = result["data_schema"].schema[CONF_PROJECTOR]
    return [(option["value"], option["label"]) for option in selector.config["options"]]


async def test_search_lists_projectors(
    hass: HomeAssistant,
    projector: FakeProjector,
    at_port: None,
    mock_search: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    del projector.values["%1NAME"]
    mock_search.return_value = [
        _reply("127.0.0.1", "Cinema "),
        _reply("127.0.0.1", "Cinema"),  # answered twice
        _reply(OTHER_HOST, ""),
        _reply("192.0.2.40", "x", code="ERST"),  # not a search reply
    ]
    result = await _search(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pick_projector"
    assert _choices(result) == [
        ("127.0.0.1", "Cinema (127.0.0.1)"),
        (OTHER_HOST, f"Valerion ({OTHER_HOST})"),
        (MANUAL_ENTRY, MANUAL_ENTRY),
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PROJECTOR: "127.0.0.1"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Without a name over AWOL Link, the network name is the title.
    assert result["title"] == "Cinema"
    assert result["data"] == {CONF_HOST: "127.0.0.1", CONF_PORT: projector.port}
    assert result["result"].unique_id is None


async def test_search_leaves_out_configured_projectors(
    hass: HomeAssistant, mock_search: AsyncMock
) -> None:
    _entry().add_to_hass(hass)
    mock_search.return_value = [_reply(OTHER_HOST, "Cinema"), _reply("192.0.2.40", "Bedroom")]
    result = await _search(hass)
    assert _choices(result) == [
        ("192.0.2.40", "Bedroom (192.0.2.40)"),
        (MANUAL_ENTRY, MANUAL_ENTRY),
    ]


async def test_search_with_only_configured_projectors_shows_manual_form(
    hass: HomeAssistant, mock_search: AsyncMock
) -> None:
    _entry().add_to_hass(hass)
    mock_search.return_value = [_reply(OTHER_HOST, "Cinema")]
    result = await _search(hass)
    assert result["step_id"] == "user"


async def test_search_finds_nothing_shows_manual_form(
    hass: HomeAssistant, mock_search: AsyncMock
) -> None:
    result = await _search(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert mock_search.await_count == 1


async def test_search_error_shows_manual_form(hass: HomeAssistant, mock_search: AsyncMock) -> None:
    mock_search.side_effect = OSError("network unreachable")
    result = await _search(hass)
    assert result["step_id"] == "user"


async def test_search_manual_choice(
    hass: HomeAssistant,
    projector: FakeProjector,
    mock_search: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    mock_search.return_value = [_reply(OTHER_HOST, "Cinema")]
    result = await _search(hass)
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, {CONF_PROJECTOR: MANUAL_ENTRY})
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_HOST: "127.0.0.1", CONF_PORT: projector.port}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # The search ran only once.
    assert mock_search.await_count == 1


async def test_search_projector_needs_security_code(
    hass: HomeAssistant, socket_enabled: None, mock_search: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    fake = FakeProjector(security_code="1234", values=dict(DEFAULT_VALUES))
    await fake.start()
    port = fake.port
    mock_search.return_value = [_reply("127.0.0.1", "Cinema")]
    try:
        with patch("custom_components.valerion.config_flow.DISCOVERY_PORT", fake.port):
            result = await _search(hass)
            flow_id = result["flow_id"]
            result = await hass.config_entries.flow.async_configure(
                flow_id, {CONF_PROJECTOR: "127.0.0.1"}
            )
            assert result["step_id"] == "security_code"
            assert result["description_placeholders"] == {"name": "Cinema", "host": "127.0.0.1"}
            result = await hass.config_entries.flow.async_configure(
                flow_id, {CONF_SECURITY_CODE: "1234"}
            )
    finally:
        await fake.stop()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: port,
        CONF_SECURITY_CODE: "1234",
    }


async def test_search_projector_not_answering_shows_manual_form(
    hass: HomeAssistant, mock_search: AsyncMock
) -> None:
    mock_search.return_value = [_reply(OTHER_HOST, "Cinema")]
    result = await _search(hass)
    with patch(
        "custom_components.valerion.config_flow._async_validate",
        side_effect=AwolLinkUnresponsiveError("silent"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PROJECTOR: OTHER_HOST}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "projector_asleep"}
    # The address is filled in, so the user can try again or change it.
    suggested = {
        str(key): key.description["suggested_value"]
        for key in result["data_schema"].schema
        if key.description and "suggested_value" in key.description
    }
    assert suggested[CONF_HOST] == OTHER_HOST
