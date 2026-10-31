"""Tests for the valerion.send_raw_command action."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.valerion.const import DOMAIN
from custom_components.valerion.coordinator import ValerionCoordinator
from custom_components.valerion.services import SERVICE_SEND_RAW_COMMAND
from tests.lib.fake_projector import FakeProjector


async def _send(hass: HomeAssistant, **data: str) -> dict[str, str]:
    response = await hass.services.async_call(
        DOMAIN, SERVICE_SEND_RAW_COMMAND, data, blocking=True, return_response=True
    )
    assert response is not None
    return dict(response)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("command", "sent", "reply"),
    [
        ("%1POWR ?", "%1POWR ?", "%1POWR=1"),
        ("%3volm 20", "%3VOLM 20", "%3VOLM=OK"),
        # Unknown class 3 codes keep the ? in the reply header on the Pro2.
        ("%3ZZZZ ?", "%3ZZZZ ?", "%3ZZZZ=ERR1"),
    ],
)
async def test_send_raw_command(
    hass: HomeAssistant,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
    command: str,
    sent: str,
    reply: str,
) -> None:
    assert await _send(hass, command=command) == {"command": sent, "reply": reply}
    assert sent in projector.received


async def test_projector_errors_are_returned(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # The projector's own answer is the useful part, so ERRx is not raised.
    projector.unavailable.add("%3ASPR")
    response = await _send(hass, config_entry=coordinator.config_entry.entry_id, command="%3ASPR 4")
    assert response == {"command": "%3ASPR 4", "reply": "%3ASPR=ERR3"}


async def test_invalid_line(hass: HomeAssistant, coordinator: ValerionCoordinator) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await _send(hass, command="POWR on")
    assert err.value.translation_key == "invalid_raw_command"


async def test_projector_not_loaded(
    hass: HomeAssistant, coordinator: ValerionCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    with pytest.raises(ServiceValidationError):
        await _send(hass, command="%1POWR ?")
