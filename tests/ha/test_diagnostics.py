"""Tests for the diagnostics download."""

from __future__ import annotations

import json
from unittest.mock import patch

from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from custom_components.valerion.const import CONF_MAC_ETHERNET
from custom_components.valerion.coordinator import ValerionCoordinator
from custom_components.valerion.lib import protocol
from tests.lib.fake_projector import FakeProjector

from .conftest import PROJECTOR_MAC


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
    mock_config_entry: MockConfigEntry,
) -> None:
    # A learned lock and a Wake-on-LAN attempt, so every section has content.
    projector.refused["%3LASL"] = "ERR3"
    with pytest.raises(HomeAssistantError):
        await coordinator.async_send(protocol.LASER_LEVEL, 5)
    with patch(
        "custom_components.valerion.coordinator.send_magic_packet",
        return_value=["255.255.255.255", "127.0.0.1"],
    ):
        await coordinator._async_wake(PROJECTOR_MAC)
    await coordinator.scenes.async_save("Movie night", settings={"laser_level": 4})

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
    # The fake projector listens on a random port, and the wake time changes.
    assert diagnostics == snapshot(exclude=props("port", "time"))
    assert diagnostics["entry"]["data"]["host"] == "**REDACTED**"
    assert diagnostics["state"]["identity"]["name"] == "**REDACTED**"
    assert diagnostics["state"]["values"]["NAME"] == "**REDACTED**"
    # Scene names are the user's own words: only the number is shown.
    assert diagnostics["scenes"] == {"count": 1}
    assert "Movie night" not in json.dumps(diagnostics)


async def test_diagnostics_never_show_the_address(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    coordinator: ValerionCoordinator,
    mock_config_entry: MockConfigEntry,
) -> None:
    # Error messages name the address, and they are not under a redacted key.
    host = coordinator.client.host
    coordinator.async_set_updated_data(
        coordinator._handle_unreachable(f"timeout connecting to {host}:4352")
    )
    coordinator.last_wake = {"time": "now", "error": f"cannot send to {host}"}

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    assert host not in json.dumps(diagnostics)
    assert diagnostics["state"]["last_error"] == "timeout connecting to **REDACTED**:4352"


async def test_diagnostics_never_show_a_mac(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    coordinator: ValerionCoordinator,
    mock_config_entry: MockConfigEntry,
) -> None:
    macs = {CONF_MAC: "00:00:5e:00:53:01", CONF_MAC_ETHERNET: "00:00:5e:00:53:02"}
    hass.config_entries.async_update_entry(mock_config_entry, options=macs)
    coordinator.macs = tuple(macs.values())
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    text = json.dumps(diagnostics)
    assert "00:00:5e" not in text
    assert diagnostics["wake_on_lan"]["mac_count"] == 2
