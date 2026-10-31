"""Tests for the picture mode and picture setting selects."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from custom_components.valerion.coordinator import ValerionCoordinator
from tests.lib.fake_projector import FakeProjector

from .conftest import entity_id, poll, poll_settings, setup_entry


async def _select(hass: HomeAssistant, key: str, option: str) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id(hass, SELECT_DOMAIN, key), ATTR_OPTION: option},
        blocking=True,
    )


def _state(hass: HomeAssistant, key: str) -> str:
    state = hass.states.get(entity_id(hass, SELECT_DOMAIN, key))
    assert state is not None
    return state.state


async def _play_sdr(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    """Switch the fake to a 1080p SDR signal in Theater mode, gamma 2.2."""
    projector.values.update(
        {
            "%3SINF": "1920*1080p@60Hz 0 1 1 0 0",
            "%3PICT": "Theater",
            "%3PICL": "Standard,Vivid,Theater,FILMMAKER MODE",
            "%3GAMA": "1",
        }
    )
    await poll_settings(hass, coordinator)


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
) -> None:
    with patch("custom_components.valerion.PLATFORMS", [Platform.SELECT]):
        await setup_entry(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_picture_mode(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    await _select(hass, "picture_mode", "HDR Vivid")
    assert "%3PICT HDR Vivid" in projector.received
    assert _state(hass, "picture_mode") == "HDR Vivid"


async def test_active_mode_missing_from_list_is_offered(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.values["%3PICT"] = "IMAX Mode"
    await poll(hass, coordinator)
    state = hass.states.get(entity_id(hass, SELECT_DOMAIN, "picture_mode"))
    assert state.state == "IMAX Mode"
    assert state.attributes[ATTR_OPTIONS] == [
        "HDR Standard",
        "HDR Vivid",
        "HDR Theater",
        "IMAX Mode",
    ]


async def test_gamma_locked_in_hdr10_settable_in_sdr(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    assert _state(hass, "gamma") == STATE_UNAVAILABLE

    await _play_sdr(hass, projector, coordinator)
    state = hass.states.get(entity_id(hass, SELECT_DOMAIN, "gamma"))
    assert state.state == "gamma_2_2"
    assert state.attributes[ATTR_OPTIONS] == ["gamma_2_0", "gamma_2_2", "gamma_2_4", "bt1886"]
    await _select(hass, "gamma", "gamma_2_4")
    assert "%3GAMA 2" in projector.received
    assert _state(hass, "gamma") == "gamma_2_4"
    # Dynamic tone mapping is HDR only.
    assert _state(hass, "dynamic_tone_mapping") == STATE_UNAVAILABLE


async def test_reported_value_that_cannot_be_set(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # SMPTE 2084 is shown while the projector reports it, but cannot be chosen.
    await _play_sdr(hass, projector, coordinator)
    projector.values["%3GAMA"] = "4"
    await poll_settings(hass, coordinator)
    state = hass.states.get(entity_id(hass, SELECT_DOMAIN, "gamma"))
    assert state.state == "smpte2084"
    assert "smpte2084" in state.attributes[ATTR_OPTIONS]
    with pytest.raises(ServiceValidationError) as err:
        await _select(hass, "gamma", "smpte2084")
    assert err.value.translation_key == "value_not_settable"


async def test_unknown_value(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.values["%3ASPR"] = "42"
    await poll_settings(hass, coordinator)
    assert _state(hass, "aspect_ratio") == STATE_UNKNOWN


async def test_settings(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    await _select(hass, "aspect_ratio", "ratio_21_9")
    await _select(hass, "dynamic_tone_mapping", "high")
    await _select(hass, "color_temperature", "cool")
    await _select(hass, "enhanced_black_level", "high")
    await _select(hass, "motion_enhancement", "smooth")
    for line in ("%3ASPR 4", "%3DYTM 2", "%3CLTP 3", "%3ENBL 3", "%3MOTN 5"):
        assert line in projector.received
    assert _state(hass, "motion_enhancement") == "smooth"


async def test_refused_value_is_explained(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # The Pro2 has no Film motion mode (ERR2 in every format).
    projector.refused["%3MOTN"] = "ERR2"
    with pytest.raises(HomeAssistantError) as err:
        await _select(hass, "motion_enhancement", "film")
    assert err.value.translation_key == "motion_mode_rejected"
    assert _state(hass, "motion_enhancement") == "off"


async def test_locked_setting_becomes_unavailable(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.refused["%3ENBL"] = "ERR3"
    with pytest.raises(HomeAssistantError) as err:
        await _select(hass, "enhanced_black_level", "high")
    assert err.value.translation_key == "setting_locked"
    assert _state(hass, "enhanced_black_level") == STATE_UNAVAILABLE
