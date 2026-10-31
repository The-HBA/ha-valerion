"""Tests for the setup dialog (config flow) and the settings dialog (options flow)."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.valerion.const import CONF_SECURITY_CODE, DOMAIN
from custom_components.valerion.lib import (
    AwolLinkAuthError,
    AwolLinkConnectionError,
    AwolLinkRefusedError,
    AwolLinkUnresponsiveError,
)
from tests.lib.fake_projector import DEFAULT_VALUES, FakeProjector

from .conftest import PROJECTOR_MAC


@pytest.fixture
def mock_setup_entry() -> Iterator[AsyncMock]:
    """Skip setting up the projector after the flow creates the entry."""
    with patch("custom_components.valerion.async_setup_entry", return_value=True) as mock:
        yield mock


async def _start(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    return result["flow_id"]


async def test_user_flow_creates_entry(
    hass: HomeAssistant, projector: FakeProjector, mock_setup_entry: AsyncMock
) -> None:
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {CONF_HOST: " 127.0.0.1 ", CONF_PORT: projector.port, CONF_MAC: "F0-ED-51-C4-4C-A8"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["data"] == {
        CONF_HOST: "127.0.0.1",
        CONF_PORT: projector.port,
        CONF_MAC: PROJECTOR_MAC,
    }
    assert result["result"].unique_id == PROJECTOR_MAC
    assert len(mock_setup_entry.mock_calls) == 1
    # The flow's test session was closed again.
    assert projector.connections == 1


async def test_user_flow_without_mac_or_name(
    hass: HomeAssistant, projector: FakeProjector, mock_setup_entry: AsyncMock
) -> None:
    del projector.values["%1NAME"]
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_HOST: "127.0.0.1", CONF_PORT: projector.port}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Without a projector name the model becomes the title.
    assert result["title"] == "VisionMaster Pro2"
    assert result["data"] == {CONF_HOST: "127.0.0.1", CONF_PORT: projector.port}
    assert result["result"].unique_id is None


async def test_user_flow_without_name_or_model(
    hass: HomeAssistant, projector: FakeProjector, mock_setup_entry: AsyncMock
) -> None:
    del projector.values["%1NAME"]
    del projector.values["%1INF2"]
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_HOST: "127.0.0.1", CONF_PORT: projector.port}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Valerion"


async def test_user_flow_with_security_code(
    hass: HomeAssistant, socket_enabled: None, mock_setup_entry: AsyncMock
) -> None:
    fake = FakeProjector(security_code="1234", values=dict(DEFAULT_VALUES))
    await fake.start()
    try:
        flow_id = await _start(hass)
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_HOST: "127.0.0.1", CONF_PORT: fake.port, CONF_SECURITY_CODE: "9999"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_HOST: "127.0.0.1", CONF_PORT: fake.port, CONF_SECURITY_CODE: "1234"}
        )
    finally:
        await fake.stop()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SECURITY_CODE] == "1234"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (AwolLinkUnresponsiveError("no greeting"), "projector_asleep"),
        (AwolLinkAuthError("wrong code"), "invalid_auth"),
        (AwolLinkRefusedError("refused"), "awol_link_off"),
        (AwolLinkConnectionError("unreachable"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_flow_errors_and_recovery(
    hass: HomeAssistant,
    projector: FakeProjector,
    mock_setup_entry: AsyncMock,
    error: Exception,
    reason: str,
) -> None:
    flow_id = await _start(hass)
    user_input = {CONF_HOST: "127.0.0.1", CONF_PORT: projector.port}
    with patch("custom_components.valerion.config_flow._async_validate", side_effect=error):
        result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": reason}

    # The user fixes the problem and submits again.
    result = await hass.config_entries.flow.async_configure(flow_id, user_input)
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        ({CONF_HOST: "not a host!"}, {CONF_HOST: "invalid_host"}),
        ({CONF_HOST: "127.0.0.1", CONF_MAC: "zz:zz"}, {CONF_MAC: "invalid_mac"}),
    ],
)
async def test_user_flow_invalid_input(
    hass: HomeAssistant,
    projector: FakeProjector,
    user_input: dict[str, str],
    errors: dict[str, str],
) -> None:
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_PORT: projector.port, **user_input}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors
    # Invalid input never reaches the projector.
    assert projector.connections == 0


async def test_user_flow_duplicate_host(
    hass: HomeAssistant, projector: FakeProjector, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_HOST: "127.0.0.1", CONF_PORT: projector.port}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_known_mac_updates_host(
    hass: HomeAssistant, projector: FakeProjector
) -> None:
    # The projector got a new IP address and is added again with its MAC.
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=PROJECTOR_MAC,
        data={CONF_HOST: "10.10.30.50", CONF_PORT: 4352, CONF_MAC: PROJECTOR_MAC},
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    flow_id = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {CONF_HOST: "127.0.0.1", CONF_PORT: projector.port, CONF_MAC: PROJECTOR_MAC}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "127.0.0.1"
    assert entry.data[CONF_PORT] == projector.port


@pytest.mark.parametrize(
    ("mac_input", "stored"),
    [
        ("F0ED51C44CA8", PROJECTOR_MAC),
        ("", ""),  # empty removes a MAC entered during the first setup
    ],
)
async def test_options_flow_sets_and_removes_mac(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mac_input: str, stored: str
) -> None:
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_MAC: "aa:bb:cc:dd:ee:ff"}
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_MAC: "nonsense"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_MAC: "invalid_mac"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_MAC: mac_input}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_MAC: stored}
    coordinator = mock_config_entry.runtime_data
    assert coordinator.mac == (stored or None)
