"""Tests for instant updates, with real UDP packets on 127.0.0.1."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
import logging
import socket
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.valerion.const import CONF_STATUS_NOTIFICATIONS, DOMAIN
from custom_components.valerion.coordinator import ValerionCoordinator
from custom_components.valerion.diagnostics import async_get_config_entry_diagnostics
from custom_components.valerion.notifications import ISSUE_PORT_UNAVAILABLE, _NotificationHub
from tests.lib.fake_projector import FakeProjector

from .conftest import PROJECTOR_MAC, entity_id, setup_entry

SENSOR_UNIQUE_ID = f"{PROJECTOR_MAC}_last_status_notification"


@pytest.fixture
def udp_port(socket_enabled: None) -> Iterator[int]:
    """A free UDP port, used instead of the real 4352."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    with patch("custom_components.valerion.notifications.NOTIFICATION_PORT", port):
        yield port


@pytest.fixture
def enabled_entry(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> MockConfigEntry:
    """The config entry with instant updates switched on."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_STATUS_NOTIFICATIONS: True}
    )
    return mock_config_entry


def _send(port: int, data: bytes) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        sender.sendto(data, ("127.0.0.1", port))


async def _wait_until(hass: HomeAssistant, condition: Callable[[], bool]) -> None:
    """Wait for a packet to arrive (it takes loop passes), then for what it started."""
    async with asyncio.timeout(2):
        while not condition():  # noqa: ASYNC110 - a packet sets no event
            await asyncio.sleep(0.01)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _send_and_wait(
    hass: HomeAssistant, coordinator: ValerionCoordinator, port: int, data: bytes
) -> None:
    received = coordinator.notifications_received
    _send(port, data)
    await _wait_until(hass, lambda: coordinator.notifications_received > received)


async def _unload(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_off_by_default(
    hass: HomeAssistant,
    coordinator: ValerionCoordinator,
    entity_registry: er.EntityRegistry,
) -> None:
    assert coordinator.notifications_listening is False
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, SENSOR_UNIQUE_ID) is None


async def test_message_starts_a_poll_but_is_not_trusted_as_state(
    hass: HomeAssistant,
    udp_port: int,
    projector: FakeProjector,
    enabled_entry: MockConfigEntry,
) -> None:
    await setup_entry(hass, enabled_entry)
    coordinator: ValerionCoordinator = enabled_entry.runtime_data
    sensor = entity_id(hass, "sensor", "last_status_notification")
    assert coordinator.notifications_listening is True
    assert hass.states.get(sensor).state == STATE_UNKNOWN
    connections = projector.connections

    # The message claims standby; the projector itself still says it is on.
    await _send_and_wait(hass, coordinator, udp_port, b"%2POWR=0\r")

    assert projector.connections == connections + 1
    assert coordinator.data.is_on
    assert coordinator.notifications_received == 1
    assert coordinator.last_notification_header == "%2POWR"
    assert hass.states.get(sensor).state != STATE_UNKNOWN
    await _unload(hass, enabled_entry)


async def test_a_burst_of_messages_polls_once(
    hass: HomeAssistant,
    udp_port: int,
    projector: FakeProjector,
    enabled_entry: MockConfigEntry,
) -> None:
    await setup_entry(hass, enabled_entry)
    coordinator: ValerionCoordinator = enabled_entry.runtime_data
    connections = projector.connections

    for _ in range(5):
        await _send_and_wait(hass, coordinator, udp_port, b"%2INPT=31\r")

    assert coordinator.notifications_received == 5
    # One right away; the rest wait for the 10 second limit, which has not passed.
    assert projector.connections == connections + 1
    await _unload(hass, enabled_entry)


async def test_message_from_another_address_is_ignored(
    hass: HomeAssistant,
    udp_port: int,
    projector: FakeProjector,
    enabled_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, "custom_components.valerion.notifications")
    # The packets below come from 127.0.0.1, so the projector must be elsewhere.
    with patch("custom_components.valerion.notifications.resolve_ipv4", return_value={"10.0.0.9"}):
        await setup_entry(hass, enabled_entry)
    coordinator: ValerionCoordinator = enabled_entry.runtime_data
    connections = projector.connections

    _send(udp_port, b"%2POWR=1\r")
    await _wait_until(hass, lambda: "not a configured projector" in caplog.text)

    assert coordinator.notifications_received == 0
    assert projector.connections == connections
    await _unload(hass, enabled_entry)


async def test_port_in_use_raises_a_repair_and_polling_carries_on(
    hass: HomeAssistant,
    udp_port: int,
    enabled_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as other_program:
        other_program.bind(("0.0.0.0", udp_port))
        await setup_entry(hass, enabled_entry)

        assert enabled_entry.state is ConfigEntryState.LOADED
        assert enabled_entry.runtime_data.notifications_listening is False
        assert issue_registry.async_get_issue(DOMAIN, ISSUE_PORT_UNAVAILABLE) is not None

    # The other program has gone: a reload opens the port and clears the repair.
    await hass.config_entries.async_reload(enabled_entry.entry_id)
    await hass.async_block_till_done()
    assert enabled_entry.runtime_data.notifications_listening is True
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_PORT_UNAVAILABLE) is None
    await _unload(hass, enabled_entry)


async def test_unloading_clears_the_repair(
    hass: HomeAssistant,
    udp_port: int,
    enabled_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as other_program:
        other_program.bind(("0.0.0.0", udp_port))
        await setup_entry(hass, enabled_entry)
        await _unload(hass, enabled_entry)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_PORT_UNAVAILABLE) is None


async def test_unknown_host_keeps_polling(
    hass: HomeAssistant,
    udp_port: int,
    enabled_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with patch("custom_components.valerion.notifications.resolve_ipv4", return_value=set()):
        await setup_entry(hass, enabled_entry)

    assert enabled_entry.state is ConfigEntryState.LOADED
    assert enabled_entry.runtime_data.notifications_listening is False
    assert "no IPv4 address found" in caplog.text


async def test_two_projectors_share_the_port(
    hass: HomeAssistant,
    udp_port: int,
    enabled_entry: MockConfigEntry,
) -> None:
    other = MockConfigEntry(
        domain=DOMAIN,
        title="Other room",
        unique_id="aa:bb:cc:dd:ee:ff",
        data=dict(enabled_entry.data),
        options={CONF_STATUS_NOTIFICATIONS: True},
        version=1,
        minor_version=2,
    )
    await setup_entry(hass, enabled_entry)
    other.add_to_hass(hass)
    with patch("custom_components.valerion.notifications.resolve_ipv4", return_value={"10.0.0.9"}):
        await setup_entry(hass, other)
    assert enabled_entry.runtime_data.notifications_listening is True
    assert other.runtime_data.notifications_listening is True

    # The port stays open for the first projector when the second one goes.
    await _unload(hass, other)
    await _send_and_wait(hass, enabled_entry.runtime_data, udp_port, b"%2POWR=1\r")
    assert enabled_entry.runtime_data.notifications_received == 1
    assert other.state is ConfigEntryState.NOT_LOADED

    await _unload(hass, enabled_entry)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as free:
        free.bind(("0.0.0.0", udp_port))


async def test_projectors_set_up_at_once_open_the_port_once(
    hass: HomeAssistant,
    udp_port: int,
    coordinator: ValerionCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    hub = _NotificationHub(hass)

    await asyncio.gather(
        hub.async_add({"10.0.0.1"}, coordinator), hub.async_add({"10.0.0.2"}, coordinator)
    )

    # The second to try would find the port taken, by the first.
    assert "Cannot listen" not in caplog.text
    hub.async_remove(coordinator)


async def test_options_flow_switches_it_on_and_off(
    hass: HomeAssistant,
    udp_port: int,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    await setup_entry(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    # The address to enter on the projector, as seen from here.
    assert result["description_placeholders"]["address"] == "127.0.0.1"
    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_STATUS_NOTIFICATIONS: True}
    )
    await hass.async_block_till_done()
    assert mock_config_entry.options[CONF_STATUS_NOTIFICATIONS] is True
    assert mock_config_entry.runtime_data.notifications_listening is True
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, SENSOR_UNIQUE_ID) is not None

    # The form opens with the setting as saved, and off removes the sensor.
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_STATUS_NOTIFICATIONS: False}
    )
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.notifications_listening is False
    assert entity_registry.async_get_entity_id("sensor", DOMAIN, SENSOR_UNIQUE_ID) is None


async def test_options_form_without_a_route(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    await setup_entry(hass, mock_config_entry)
    with patch("custom_components.valerion.config_flow.local_address_towards", return_value=None):
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["description_placeholders"]["address"] == "Home Assistant's IP address"


async def test_diagnostics_show_the_code_but_not_the_message(
    hass: HomeAssistant,
    udp_port: int,
    enabled_entry: MockConfigEntry,
) -> None:
    await setup_entry(hass, enabled_entry)

    await _send_and_wait(
        hass, enabled_entry.runtime_data, udp_port, b"%2LKUP=VisionMaster Pro2 x GoogleTV2891\r"
    )

    found = await async_get_config_entry_diagnostics(hass, enabled_entry)
    status = found["status_notification"]
    assert status["listening"] is True
    assert status["received"] == 1
    assert status["last_at"] is not None
    assert status["last_code"] == "%2LKUP"
    assert "GoogleTV2891" not in str(found)
    await _unload(hass, enabled_entry)
