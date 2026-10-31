"""Tests for polling, power, locks and command errors in the coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PORT,
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.valerion.const import (
    CONF_POWER_OFF_MODE,
    DOMAIN,
    INTERVAL_IDLE,
    INTERVAL_ON,
    INTERVAL_TRANSITION,
    POWER_OFF_MODE_FULL,
)
from custom_components.valerion.coordinator import Connection, PowerState, ValerionCoordinator
from custom_components.valerion.lib import AwolLinkConnectionError, Command, key_press, protocol
from tests.lib.fake_projector import FakeProjector

from .conftest import ENTRY_ID, PROJECTOR_MAC, poll, poll_settings, setup_entry

COORDINATOR = "custom_components.valerion.coordinator"
LOCK_STORE = f"{DOMAIN}.{ENTRY_ID}.locks"


def _queries(projector: FakeProjector, code: str) -> int:
    """Return how often the projector was asked for ``code``."""
    return sum(1 for line in projector.received if line[2:6] == code and line.endswith(" ?"))


async def _save_locks(hass: HomeAssistant) -> None:
    """Write the learned locks now, as Home Assistant does when it shuts down.

    The delayed save waits for the real event-loop clock, which
    ``async_fire_time_changed`` cannot move.
    """
    hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass.async_block_till_done()


# ------------------------------------------------------------------ polling
async def test_poll_while_on(hass: HomeAssistant, coordinator: ValerionCoordinator) -> None:
    data = coordinator.data
    assert data.connection == Connection.ANSWERING
    assert data.power == PowerState.ON
    assert not data.busy
    assert data.value(protocol.INPUT) == "31"
    assert data.value(protocol.PICTURE_MODE) == "HDR Theater"
    assert data.picture_modes == ("HDR Standard", "HDR Vivid", "HDR Theater")
    assert data.signal is not None
    assert data.signal.has_signal
    # Gamma is built in as locked for HDR10.
    assert data.locked == frozenset({"GAMA"})
    assert data.identity.model == "VisionMaster Pro2"
    assert data.identity.inputs == ("30", "31", "32", "33")
    assert coordinator.update_interval == INTERVAL_ON

    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, PROJECTOR_MAC), ENTRY_ID)
    assert device is not None
    assert device.model == "VisionMaster Pro2"
    assert device.name == "Living room"
    assert device.sw_version == "V02.01.00E.Q0718"


async def test_light_standby(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # The Pro2 keeps answering in standby, with POWR 0.
    projector.values["%1POWR"] = "0"
    projector.received.clear()
    await poll(hass, coordinator)

    data = coordinator.data
    assert data.connection == Connection.ANSWERING
    assert data.power == PowerState.STANDBY
    # Only the power state is asked; values that need a running projector are dropped.
    assert projector.received == ["%1POWR ?"]
    assert data.value(protocol.INPUT) is None
    assert data.signal is None
    assert data.identity.model == "VisionMaster Pro2"
    assert coordinator.update_interval == INTERVAL_IDLE


async def test_silent_while_on_is_busy_then_standby(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # A projector that was on and stops greeting probably has another app
    # connected; it only counts as standby after three silent polls.
    coordinator.client.timeout = 0.1
    projector.silent = True
    for _ in range(3):
        await poll(hass, coordinator)
        assert coordinator.data.connection == Connection.SILENT
        assert coordinator.data.power == PowerState.ON
        assert coordinator.data.busy
        assert coordinator.data.value(protocol.INPUT) == "31"

    await poll(hass, coordinator)
    assert coordinator.data.connection == Connection.SILENT
    assert coordinator.data.power == PowerState.STANDBY
    assert not coordinator.data.busy
    assert coordinator.data.value(protocol.INPUT) is None
    assert coordinator.update_interval == INTERVAL_IDLE

    # Answering again: on, identity read again.
    projector.silent = False
    projector.received.clear()
    await poll(hass, coordinator)
    assert coordinator.data.connection == Connection.ANSWERING
    assert coordinator.data.power == PowerState.ON
    assert "%2SVER ?" in projector.received


async def test_silent_after_standby_is_not_busy(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.values["%1POWR"] = "0"
    await poll(hass, coordinator)
    coordinator.client.timeout = 0.1
    projector.silent = True
    await poll(hass, coordinator)
    assert coordinator.data.connection == Connection.SILENT
    assert coordinator.data.power == PowerState.STANDBY
    assert not coordinator.data.busy


async def test_refused_means_awol_link_off(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    await projector.stop()
    await poll(hass, coordinator)
    assert coordinator.data.connection == Connection.REFUSED
    assert coordinator.data.power is None
    assert coordinator.data.value(protocol.INPUT) is None
    assert coordinator.data.last_error is not None
    assert coordinator.update_interval == INTERVAL_IDLE


async def test_unreachable_means_off(hass: HomeAssistant, coordinator: ValerionCoordinator) -> None:
    with patch.object(
        coordinator.client, "_open", side_effect=AwolLinkConnectionError("no route to host")
    ):
        await poll(hass, coordinator)
    assert coordinator.data.connection == Connection.UNREACHABLE
    assert coordinator.data.power == PowerState.OFF
    assert coordinator.data.last_error == "no route to host"
    assert coordinator.data.value(protocol.INPUT) is None


async def test_unavailable_and_back_are_logged_once(
    hass: HomeAssistant,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="custom_components.valerion")
    with patch.object(
        coordinator.client, "_open", side_effect=AwolLinkConnectionError("no route to host")
    ):
        await poll(hass, coordinator, times=3)
    await poll(hass, coordinator, times=2)
    messages = [r.getMessage() for r in caplog.records if r.name.endswith("coordinator")]
    assert messages.count("Projector at 127.0.0.1 is unavailable: no route to host") == 1
    assert messages.count("Projector at 127.0.0.1 is back online") == 1


async def test_slow_tier_about_once_a_minute(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # The core and fast tiers are asked on every poll, the picture settings
    # only on every sixth.
    projector.received.clear()
    await poll(hass, coordinator, times=6)
    assert _queries(projector, "INPT") == 6
    assert _queries(projector, "SINF") == 6
    assert _queries(projector, "GAMA") == 1
    assert _queries(projector, "FANS") == 1
    # Identity only once, after power-on.
    assert _queries(projector, "SVER") == 0


async def test_settings_read_as_soon_as_an_entity_needs_them(
    hass: HomeAssistant, projector: FakeProjector, mock_config_entry: MockConfigEntry
) -> None:
    # The first poll runs before the entities exist. Without the picture
    # mode select (whose mode list check also triggers a read), the laser
    # level must still be read on the next poll, not a minute later.
    with patch("custom_components.valerion.PLATFORMS", [Platform.NUMBER]):
        await setup_entry(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.data.value(protocol.LASER_LEVEL) == "7"


async def test_picture_mode_change_rereads_settings(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    await poll(hass, coordinator)  # leave the slow-tier poll behind
    projector.received.clear()
    # The projector applies the new mode's own settings.
    projector.values["%3ENBL"] = "3"

    await coordinator.async_set_picture_mode("HDR Vivid")
    await hass.async_block_till_done()

    assert "%3PICT HDR Vivid" in projector.received
    assert _queries(projector, "ENBL") == 1
    assert coordinator.data.value(protocol.PICTURE_MODE) == "HDR Vivid"
    assert coordinator.data.value(protocol.ENHANCED_BLACK_LEVEL) == "3"


async def test_same_picture_mode_is_not_sent(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # Re-sending the active mode returns ERR4 on the Pro2 (firmware bug).
    projector.received.clear()
    await coordinator.async_set_picture_mode("HDR Theater")
    assert projector.received == []


async def test_new_signal_format_rereads_list_once(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    await poll(hass, coordinator)
    # SDR starts: the active mode is not in the known (HDR) list.
    projector.values["%3SINF"] = "1920*1080p@60Hz 0 1 1 0 0"
    projector.values["%3PICT"] = "Theater"
    projector.values["%3PICL"] = "Standard,Vivid,Theater"
    projector.received.clear()
    await poll(hass, coordinator)
    assert _queries(projector, "PICL") == 1
    assert coordinator.data.picture_modes == ("Standard", "Vivid", "Theater")
    # Dynamic tone mapping is built in as locked for SDR.
    assert coordinator.data.locked == frozenset({"DYTM"})

    # A list that never contains the active mode is read only once per mode.
    projector.values["%3PICT"] = "FILMMAKER MODE"
    projector.received.clear()
    await poll(hass, coordinator, times=2)
    assert _queries(projector, "PICL") == 1


async def test_err3_on_query_marks_setting_unavailable(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.unavailable.add("%3DYTM")
    await poll_settings(hass, coordinator)
    assert "DYTM" in coordinator.data.unavailable
    assert coordinator.data.is_locked(protocol.DYNAMIC_TONE_MAPPING)
    assert coordinator.data.value(protocol.DYNAMIC_TONE_MAPPING) is None

    # Kept between slow polls, cleared once it is read again.
    await poll(hass, coordinator)
    assert "DYTM" in coordinator.data.unavailable
    projector.unavailable.clear()
    await poll_settings(hass, coordinator)
    assert "DYTM" not in coordinator.data.unavailable
    assert coordinator.data.value(protocol.DYNAMIC_TONE_MAPPING) == "1"


# ------------------------------------------------------------- learned locks
async def test_refused_setting_is_learned_and_forgotten(
    hass: HomeAssistant,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
    hass_storage: dict[str, Any],
) -> None:
    projector.refused["%3LASL"] = "ERR3"
    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_send(protocol.LASER_LEVEL, 5)
    assert err.value.translation_key == "setting_locked"
    assert coordinator.data.locked == frozenset({"GAMA", "LASL"})

    await _save_locks(hass)
    assert hass_storage[LOCK_STORE]["data"] == {
        "firmware": "V02.01.00E.Q0718",
        "learned": [{"hdr": "hdr10", "picture_mode": "HDR Theater", "code": "LASL"}],
        "unsupported": [],
    }

    # Only for this signal format and picture mode.
    projector.values["%3PICT"] = "HDR Vivid"
    await poll(hass, coordinator)
    assert coordinator.data.locked == frozenset({"GAMA"})

    projector.values["%3PICT"] = "HDR Theater"
    await poll(hass, coordinator)
    assert "LASL" in coordinator.data.locked
    await coordinator.async_forget_locks()
    assert coordinator.data.locked == frozenset({"GAMA"})
    await _save_locks(hass)
    assert hass_storage[LOCK_STORE]["data"]["learned"] == []


async def test_3d_locks_stay_apart_from_2d(
    hass: HomeAssistant,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
    hass_storage: dict[str, Any],
) -> None:
    # An MVC film: frame packing reads as SDR, with the SDR picture modes.
    projector.values["%3SINF"] = "1920*2205p@24Hz 0 3 1 0 0"
    projector.values["%3PICT"] = "FILMMAKER MODE"
    projector.values["%3PICL"] = "Standard,Theater,FILMMAKER MODE"
    await poll(hass, coordinator)
    assert coordinator.data.locked == frozenset({"ASPR", "MOTN", "DYTM"})

    projector.refused["%3LASL"] = "ERR3"
    with pytest.raises(HomeAssistantError):
        await coordinator.async_send(protocol.LASER_LEVEL, 5)
    assert "LASL" in coordinator.data.locked
    await _save_locks(hass)
    assert hass_storage[LOCK_STORE]["data"]["learned"] == [
        {"hdr": "3d", "picture_mode": "FILMMAKER MODE", "code": "LASL"}
    ]

    # The same picture mode with a 2D SDR film: only the SDR lock.
    projector.values["%3SINF"] = "1920*1080p@24Hz 0 3 1 0 0"
    await poll(hass, coordinator)
    assert coordinator.data.locked == frozenset({"DYTM"})


async def test_refusal_of_current_value_is_not_learned(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # Re-sending the current value can be refused for other reasons
    # (aspect ratio without a signal), so it says nothing about a lock.
    projector.refused["%3LASL"] = "ERR3"
    with pytest.raises(HomeAssistantError):
        await coordinator.async_send(protocol.LASER_LEVEL, 7)
    assert coordinator.locks_as_dict()["learned"] == []


async def test_locks_survive_a_restart(
    hass: HomeAssistant,
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    hass_storage[LOCK_STORE] = {
        "version": 1,
        "minor_version": 1,
        "key": LOCK_STORE,
        "data": {
            "firmware": "V02.01.00E.Q0718",
            "learned": [{"hdr": "hdr10", "picture_mode": "HDR Theater", "code": "ENBL"}],
            "unsupported": ["LSMN"],
        },
    }
    await setup_entry(hass, mock_config_entry)
    data = mock_config_entry.runtime_data.data
    assert data.locked == frozenset({"GAMA", "ENBL"})
    assert data.unsupported == frozenset({"LSMN"})


async def test_firmware_update_clears_learned_locks(
    hass: HomeAssistant,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
    hass_storage: dict[str, Any],
) -> None:
    projector.refused["%3LASL"] = "ERR3"
    with pytest.raises(HomeAssistantError):
        await coordinator.async_send(protocol.LASER_LEVEL, 5)
    assert "LASL" in coordinator.data.locked

    # A firmware update restarts the projector; identity is read after power-on.
    projector.values["%2SVER"] = "V02.02.00E.Q0801 83 OEM01.0.0.0"
    projector.values["%1POWR"] = "0"
    await poll(hass, coordinator)
    projector.values["%1POWR"] = "1"
    await poll(hass, coordinator)

    assert coordinator.data.locked == frozenset({"GAMA"})
    await _save_locks(hass)
    assert hass_storage[LOCK_STORE]["data"]["firmware"] == "V02.02.00E.Q0801"
    assert hass_storage[LOCK_STORE]["data"]["learned"] == []
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, PROJECTOR_MAC), ENTRY_ID)
    assert device is not None
    assert device.sw_version == "V02.02.00E.Q0801"


async def test_lens_menu_refused_in_standby_is_not_learned(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # In standby a refusal says nothing about the model.
    projector.values["%1POWR"] = "0"
    await poll(hass, coordinator)
    projector.unavailable.add("%3LSMN")
    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_press_keys([key_press("lens_shift")], delay=0)
    assert err.value.translation_key == "lens_menu_unavailable"
    assert coordinator.data.unsupported == frozenset()


# ----------------------------------------------------------------- power
async def test_power_off_and_on(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    await coordinator.async_power_off()
    assert "%1POWR 0" in projector.received
    assert coordinator.data.power == PowerState.STANDBY
    assert coordinator.update_interval == INTERVAL_TRANSITION
    # A refresh follows in the background.
    await hass.async_block_till_done(wait_background_tasks=True)
    assert coordinator.data.connection == Connection.ANSWERING

    projector.received.clear()
    await coordinator.async_power_on()
    assert projector.received == ["%1POWR 1"]
    await poll(hass, coordinator)
    assert coordinator.data.power == PowerState.ON
    # Fast polls while the projector warms up.
    assert coordinator.update_interval == INTERVAL_TRANSITION


async def test_power_off_full_from_options(
    hass: HomeAssistant, projector: FakeProjector, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_POWER_OFF_MODE: POWER_OFF_MODE_FULL}
    )
    await setup_entry(hass, mock_config_entry)
    await mock_config_entry.runtime_data.async_power_off()
    assert "%1POWR 2" in projector.received
    assert mock_config_entry.runtime_data.data.power == PowerState.OFF


async def test_power_on_when_already_warming_up(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # ERR3 on POWR 1 means it is on or warming up: no error, no retry.
    projector.refused["%1POWR"] = "ERR3"
    projector.received.clear()
    await coordinator.async_power_on()
    assert projector.received.count("%1POWR 1") == 1


@pytest.fixture
async def mac_entry(hass: HomeAssistant, projector: FakeProjector) -> MockConfigEntry:
    """A projector set up with a MAC address, so turn on sends Wake-on-LAN."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living room",
        unique_id=PROJECTOR_MAC,
        entry_id=ENTRY_ID,
        data={CONF_HOST: "127.0.0.1", CONF_PORT: projector.port, CONF_MAC: PROJECTOR_MAC},
        version=1,
        minor_version=2,
    )
    await setup_entry(hass, entry)
    return entry


async def test_power_on_sends_wake_on_lan(
    hass: HomeAssistant, projector: FakeProjector, mac_entry: MockConfigEntry
) -> None:
    coordinator: ValerionCoordinator = mac_entry.runtime_data
    coordinator.client.timeout = 0.1
    projector.silent = True  # deep standby

    async def wake(mac: str, targets: tuple[str, ...]) -> list[str]:
        projector.silent = False
        return list(targets)

    with patch(f"{COORDINATOR}.send_magic_packet", side_effect=wake) as send:
        await coordinator.async_power_on()
    await hass.async_block_till_done(wait_background_tasks=True)

    send.assert_called_once_with(PROJECTOR_MAC, targets=("255.255.255.255", "127.0.0.1"))
    assert "%1POWR 1" in projector.received
    assert coordinator.last_wake is not None
    assert coordinator.last_wake["sent_to"] == ["broadcast", "projector"]


async def test_wake_on_lan_failure_is_recorded(
    hass: HomeAssistant, projector: FakeProjector, mac_entry: MockConfigEntry
) -> None:
    coordinator: ValerionCoordinator = mac_entry.runtime_data
    with patch(f"{COORDINATOR}.send_magic_packet", side_effect=OSError("network unreachable")):
        await coordinator.async_power_on()
    assert coordinator.last_wake is not None
    assert coordinator.last_wake["error"] == "network unreachable"
    # The projector was answering anyway.
    assert "%1POWR 1" in projector.received


async def test_power_on_timeout_with_mac(
    hass: HomeAssistant, projector: FakeProjector, mac_entry: MockConfigEntry
) -> None:
    coordinator: ValerionCoordinator = mac_entry.runtime_data
    coordinator.client.timeout = 0.1
    projector.silent = True
    with (
        patch(f"{COORDINATOR}.POWER_ON_TIMEOUT", timedelta(0)),
        patch(f"{COORDINATOR}.send_magic_packet", AsyncMock(return_value=[])),
        pytest.raises(HomeAssistantError) as err,
    ):
        await coordinator.async_power_on()
    assert err.value.translation_key == "power_on_timeout"


async def test_power_on_without_mac_explains_it(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    coordinator.client.timeout = 0.1
    projector.silent = True
    with (
        patch(f"{COORDINATOR}.POWER_ON_TIMEOUT", timedelta(0)),
        pytest.raises(HomeAssistantError) as err,
    ):
        await coordinator.async_power_on()
    assert err.value.translation_key == "power_on_needs_mac"


async def test_power_on_retries_until_greeted(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    coordinator.client.timeout = 0.1
    projector.silent = True
    attempts = 0

    async def sleep(_: float) -> None:
        # The pause between two attempts; the projector wakes after the second.
        nonlocal attempts
        attempts += 1
        projector.silent = attempts < 2

    # Only the coordinator's own pauses are replaced, not Home Assistant's.
    with patch(f"{COORDINATOR}.asyncio", SimpleNamespace(sleep=sleep)):
        await coordinator.async_power_on()
    assert attempts == 2
    assert "%1POWR 1" in projector.received


# -------------------------------------------------------- command errors
@pytest.mark.parametrize(
    ("command", "value", "error", "translation_key"),
    [
        (protocol.MOTION_ENHANCEMENT, 2, "ERR2", "motion_mode_rejected"),
        (protocol.COLOR_TEMPERATURE, 0, "ERR2", "color_temperature_rejected"),
        (protocol.ASPECT_RATIO, 4, "ERR2", "aspect_ratio_rejected"),
        (protocol.ENHANCED_BLACK_LEVEL, 2, "ERR3", "setting_locked"),
        (protocol.VOLUME, 50, "ERR2", "command_rejected"),
        (protocol.VOLUME, 50, "ERR4", "command_rejected"),
    ],
)
async def test_refusals_are_explained(
    hass: HomeAssistant,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
    command: Command,
    value: int,
    error: str,
    translation_key: str,
) -> None:
    projector.refused[command.header] = error
    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_send(command, value)
    assert err.value.translation_key == translation_key


async def test_command_while_silent(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    coordinator.client.timeout = 0.1
    projector.silent = True
    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_send(protocol.VOLUME, 50)
    assert err.value.translation_key == "projector_asleep"


async def test_command_while_refused(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    await projector.stop()
    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_send(protocol.VOLUME, 50)
    assert err.value.translation_key == "cannot_connect"


async def test_set_without_read_back_keeps_sent_value(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # Some codes can be set but not read back; the sent value is shown.
    original = projector._reply

    def reply(header: str, argument: str) -> str:
        if header == "%3ASPR" and argument == "?":
            return "%3ASPR=ERR2"
        return original(header, argument)

    with patch.object(projector, "_reply", side_effect=reply):
        await coordinator.async_send(protocol.ASPECT_RATIO, 4)
    assert coordinator.data.value(protocol.ASPECT_RATIO) == "4"
