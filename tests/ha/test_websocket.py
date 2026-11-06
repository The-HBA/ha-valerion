"""Tests for the websocket commands the remote card uses."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.valerion.const import (
    CONF_SECURITY_CODE,
    CONF_STATUS_NOTIFICATIONS,
    DOMAIN,
    NAME,
)
from custom_components.valerion.coordinator import ValerionCoordinator
from custom_components.valerion.lib import DeviceIdentity
from tests.lib.fake_projector import FakeProjector

from .conftest import ENTRY_ID, PROJECTOR_MAC, entity_id, poll, setup_entry


async def _send(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, message: dict[str, Any], **kwargs: Any
) -> dict[str, Any]:
    client = await hass_ws_client(hass, **kwargs)
    await client.send_json_auto_id(message)
    return await client.receive_json()


def _device_id(hass: HomeAssistant) -> str:
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, PROJECTOR_MAC), ENTRY_ID)
    assert device is not None
    return device.id


async def test_save_list_apply_delete(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
) -> None:
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "valerion/scenes/list", "entry_id": ENTRY_ID})
    reply = await client.receive_json()
    assert reply["success"]
    assert reply["result"] == {"entry_id": ENTRY_ID, "scenes": []}

    # Without settings the current ones are captured.
    await client.send_json_auto_id(
        {"type": "valerion/scenes/save", "entry_id": ENTRY_ID, "name": "Movie night"}
    )
    reply = await client.receive_json()
    assert reply["success"]
    scene = reply["result"]["scene"]
    assert scene["name"] == "Movie night"
    assert scene["settings"]["picture_mode"] == "HDR Theater"
    assert scene["entity_id"] == "scene.living_room_movie_night"
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {
            "type": "valerion/scenes/save",
            "device_id": _device_id(hass),
            "scene_id": scene["id"],
            "name": "Movie night",
            "settings": {"picture_mode": "HDR Vivid", "laser_level": 3, "gamma": "gamma_2_2"},
        }
    )
    reply = await client.receive_json()
    assert reply["success"]
    assert reply["result"]["scene"] == {
        "id": scene["id"],
        "name": "Movie night",
        "settings": {"picture_mode": "HDR Vivid", "laser_level": 3, "gamma": "gamma_2_2"},
        "entity_id": "scene.living_room_movie_night",
    }

    await client.send_json_auto_id({"type": "valerion/scenes/list", "device_id": _device_id(hass)})
    reply = await client.receive_json()
    assert reply["result"]["scenes"] == [reply["result"]["scenes"][0]]
    assert reply["result"]["scenes"][0]["id"] == scene["id"]

    projector.received.clear()
    await client.send_json_auto_id(
        {"type": "valerion/scenes/apply", "entry_id": ENTRY_ID, "scene_id": scene["id"]}
    )
    reply = await client.receive_json()
    assert reply["success"]
    assert reply["result"] == {
        "applied": ["picture_mode", "laser_level"],
        "skipped": [{"setting": "gamma", "reason": "locked"}],
    }
    assert "%3PICT HDR Vivid" in projector.received

    await client.send_json_auto_id(
        {"type": "valerion/scenes/delete", "entry_id": ENTRY_ID, "scene_id": scene["id"]}
    )
    reply = await client.receive_json()
    assert reply["success"]
    assert reply["result"] is None
    await hass.async_block_till_done()
    assert hass.states.get("scene.living_room_movie_night") is None
    assert coordinator.scenes.scenes == []


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ({"type": "valerion/scenes/list", "entry_id": "nope"}, "projector_not_found"),
        ({"type": "valerion/scenes/list", "device_id": "nope"}, "projector_not_found"),
        ({"type": "valerion/scenes/list"}, "invalid_format"),
        (
            {"type": "valerion/scenes/list", "entry_id": ENTRY_ID, "device_id": "x"},
            "invalid_format",
        ),
        (
            {"type": "valerion/scenes/apply", "entry_id": ENTRY_ID, "scene_id": "nope"},
            "scene_not_found",
        ),
        (
            {"type": "valerion/scenes/delete", "entry_id": ENTRY_ID, "scene_id": "nope"},
            "scene_not_found",
        ),
        (
            {
                "type": "valerion/scenes/save",
                "entry_id": ENTRY_ID,
                "name": "Bad",
                "settings": {"laser_level": 99},
            },
            "invalid_settings",
        ),
        (
            {"type": "valerion/scenes/save", "entry_id": ENTRY_ID, "name": " "},
            "invalid_name",
        ),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    coordinator: ValerionCoordinator,
    message: dict[str, Any],
    code: str,
) -> None:
    reply = await _send(hass, hass_ws_client, message)
    assert not reply["success"]
    assert reply["error"]["code"] == code


async def test_error_is_translated(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, coordinator: ValerionCoordinator
) -> None:
    reply = await _send(
        hass,
        hass_ws_client,
        {
            "type": "valerion/scenes/save",
            "entry_id": ENTRY_ID,
            "name": "Bad",
            "settings": {"gamma": "smpte2084"},
        },
    )
    assert reply["error"] == {
        "code": "invalid_settings",
        "message": "smpte2084 is not a value that can be set for gamma",
        "translation_domain": DOMAIN,
        "translation_key": "invalid_scene_setting",
        "translation_placeholders": {"setting": "gamma", "value": "smpte2084"},
    }


async def test_device_of_another_integration(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, coordinator: ValerionCoordinator
) -> None:
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("other", "1")}
    )
    reply = await _send(
        hass, hass_ws_client, {"type": "valerion/scenes/list", "device_id": device.id}
    )
    assert reply["error"]["code"] == "projector_not_found"
    reply = await _send(
        hass, hass_ws_client, {"type": "valerion/scenes/list", "entry_id": other.entry_id}
    )
    assert reply["error"]["code"] == "projector_not_found"


async def test_unloaded_projector(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    coordinator: ValerionCoordinator,
    mock_config_entry: MockConfigEntry,
) -> None:
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    reply = await _send(
        hass, hass_ws_client, {"type": "valerion/scenes/list", "entry_id": ENTRY_ID}
    )
    assert reply["error"]["code"] == "projector_not_found"


async def test_apply_while_off(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
) -> None:
    scene = await coordinator.scenes.async_save("Movie night", settings={"laser_level": 5})
    projector.values["%1POWR"] = "0"
    await poll(hass, coordinator)
    reply = await _send(
        hass,
        hass_ws_client,
        {"type": "valerion/scenes/apply", "entry_id": ENTRY_ID, "scene_id": scene.id},
    )
    assert reply["error"]["code"] == "projector_off"
    assert reply["error"]["translation_key"] == "scene_projector_off"


async def test_non_admin_can_list_and_apply_but_not_edit(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
) -> None:
    scene = await coordinator.scenes.async_save("Movie night", settings={"laser_level": 5})
    client = await hass_ws_client(hass, hass_read_only_access_token)

    for message in (
        {"type": "valerion/scenes/save", "entry_id": ENTRY_ID, "name": "Mine"},
        {"type": "valerion/scenes/delete", "entry_id": ENTRY_ID, "scene_id": scene.id},
    ):
        await client.send_json_auto_id(message)
        reply = await client.receive_json()
        assert not reply["success"]
        assert reply["error"]["code"] == "unauthorized"
    assert [s.name for s in coordinator.scenes.scenes] == ["Movie night"]

    for message in (
        {"type": "valerion/scenes/list", "entry_id": ENTRY_ID},
        {"type": "valerion/scenes/apply", "entry_id": ENTRY_ID, "scene_id": scene.id},
    ):
        await client.send_json_auto_id(message)
        reply = await client.receive_json()
        assert reply["success"]
    assert "%3LASL 5" in projector.received


# ---------- valerion/card_info ----------

MANIFEST_VERSION = json.loads(
    (Path(__file__).parents[2] / "custom_components" / DOMAIN / "manifest.json").read_text()
)["version"]


async def test_card_info(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, coordinator: ValerionCoordinator
) -> None:
    for target in ({"entry_id": ENTRY_ID}, {"device_id": _device_id(hass)}):
        reply = await _send(hass, hass_ws_client, {"type": "valerion/card_info", **target})
        assert reply["success"]
        assert reply["result"] == {
            "entry_id": ENTRY_ID,
            "version": MANIFEST_VERSION,
            "model": "VisionMaster Pro2",
            "firmware": "V02.01.00E.Q0718",
            "setup": {
                "wake_on_lan": False,
                "security_code": False,
                "status_notifications": False,
                "notifications_listening": False,
                "unsupported_menus": [],
            },
        }


async def test_card_info_setup_hints(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
) -> None:
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_MAC: PROJECTOR_MAC}
    )
    await setup_entry(hass, mock_config_entry)
    coordinator: ValerionCoordinator = mock_config_entry.runtime_data
    # Changed without a reload: the hints read the entry as it is now.
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_SECURITY_CODE: "1234"},
        options={CONF_STATUS_NOTIFICATIONS: True},
    )
    coordinator.notifications_listening = True
    # A Pro2 has no motorised lens shift; the refusal is remembered.
    projector.unavailable.add("%3LSMN")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id(hass, BUTTON_DOMAIN, "button_lens_shift")},
            blocking=True,
        )

    # Read-only users see the hints too; nothing in them is secret.
    reply = await _send(
        hass,
        hass_ws_client,
        {"type": "valerion/card_info", "entry_id": ENTRY_ID},
        access_token=hass_read_only_access_token,
    )
    assert reply["success"]
    assert reply["result"]["setup"] == {
        "wake_on_lan": True,
        "security_code": True,
        "status_notifications": True,
        "notifications_listening": True,
        "unsupported_menus": ["lens_shift"],
    }
    text = json.dumps(reply["result"])
    for secret in ("1234", PROJECTOR_MAC, "127.0.0.1"):
        assert secret not in text


async def test_card_info_model_from_device_registry(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
    coordinator: ValerionCoordinator,
) -> None:
    # Not answered since the restart: the device registry still knows the model.
    coordinator.data = replace(coordinator.data, identity=DeviceIdentity())
    message = {"type": "valerion/card_info", "entry_id": ENTRY_ID}
    reply = await _send(hass, hass_ws_client, message)
    assert reply["result"]["model"] == "VisionMaster Pro2"
    assert reply["result"]["firmware"] == "V02.01.00E.Q0718"

    # Never answered: only the placeholder model, which is not shown.
    device_registry.async_update_device(_device_id(hass), model=NAME, sw_version=None)
    reply = await _send(hass, hass_ws_client, message)
    assert reply["result"]["model"] is None
    assert reply["result"]["firmware"] is None


async def test_card_info_not_found(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, coordinator: ValerionCoordinator
) -> None:
    reply = await _send(hass, hass_ws_client, {"type": "valerion/card_info", "entry_id": "nope"})
    assert reply["error"]["code"] == "projector_not_found"
