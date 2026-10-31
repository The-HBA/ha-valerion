"""Tests for the diagnostics download."""

from __future__ import annotations

from unittest.mock import patch

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

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
    # The fake projector listens on a random port, and the wake time changes.
    assert diagnostics == snapshot(exclude=props("port", "time"))
    assert diagnostics["entry"]["data"]["host"] == "**REDACTED**"
