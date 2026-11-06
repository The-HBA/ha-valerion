"""Tests for the stored picture scenes and their scene entities."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, SERVICE_TURN_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.valerion.const import DOMAIN
from custom_components.valerion.coordinator import ProjectorData, ValerionCoordinator
from custom_components.valerion.lib import protocol
from custom_components.valerion.scenes import (
    InvalidSceneNameError,
    InvalidSceneSettingsError,
    ProjectorOffError,
    SceneNotFoundError,
    SkippedSetting,
)
from tests.lib.fake_projector import FakeProjector

from .conftest import ENTRY_ID, PROJECTOR_MAC, poll, poll_settings, setup_entry

STORE_KEY = f"{DOMAIN}.{ENTRY_ID}.scenes"

#: What the fixture projector shows (4K HDR10 film): gamma is locked in HDR10.
CAPTURED = {
    "picture_mode": "HDR Theater",
    "laser_level": 7,
    "aspect_ratio": "ratio_16_9",
    "dynamic_tone_mapping": "low",
    "color_temperature": "standard",
    "enhanced_black_level": "low",
    "motion_enhancement": "off",
}
#: Every setting, in a different order than they are sent.
EVERYTHING: dict[str, Any] = {
    "motion_enhancement": "smooth",
    "enhanced_black_level": "high",
    "color_temperature": "cool",
    "dynamic_tone_mapping": "high",
    "gamma": "gamma_2_4",
    "aspect_ratio": "ratio_21_9",
    "laser_level": 3,
    "picture_mode": "HDR Vivid",
}


def _sets(projector: FakeProjector) -> list[str]:
    """Return the set commands the projector received, without the queries."""
    return [line for line in projector.received if not line.endswith(" ?")]


def _scene_entity_id(hass: HomeAssistant, scene_id: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(
        SCENE_DOMAIN, DOMAIN, f"{PROJECTOR_MAC}_scene_{scene_id}"
    )


async def _activate(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        SCENE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )


async def _switch_off(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.values["%1POWR"] = "0"
    await poll(hass, coordinator)


async def test_save_captures_current_settings(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    coordinator: ValerionCoordinator,
) -> None:
    scene = await coordinator.scenes.async_save("  Movie night ")
    await hass.async_block_till_done()

    assert scene.name == "Movie night"
    # Gamma is locked in HDR10, so it is left out.
    assert scene.settings == CAPTURED
    assert list(scene.settings) == list(CAPTURED)
    entity_id = _scene_entity_id(hass, scene.id)
    assert entity_id == "scene.living_room_movie_night"
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_FRIENDLY_NAME] == "Living room Movie night"
    entry = er.async_get(hass).async_get(entity_id)
    assert entry.device_id is not None
    assert entry.original_name == "Movie night"
    assert hass_storage[STORE_KEY]["version"] == 1
    assert hass_storage[STORE_KEY]["data"] == {
        "scenes": [{"id": scene.id, "name": "Movie night", "settings": CAPTURED}]
    }


async def test_capture_leaves_out_unknown_and_read_only_values(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # SDR: gamma is not locked, but SMPTE 2084 cannot be chosen.
    projector.values.update(
        {
            "%3SINF": "1920*1080p@60Hz 0 1 1 0 0",
            "%3PICT": "Theater",
            "%3PICL": "Standard,Vivid,Theater",
            "%3GAMA": "4",
            "%3ASPR": "42",
            "%3LASL": "high",
        }
    )
    await poll_settings(hass, coordinator)
    scene = await coordinator.scenes.async_save("Daylight")
    assert scene.settings == {
        "picture_mode": "Theater",
        "color_temperature": "standard",
        "enhanced_black_level": "low",
        "motion_enhancement": "off",
    }

    projector.values["%3GAMA"] = "1"
    await poll_settings(hass, coordinator)
    scene = await coordinator.scenes.async_save("Daylight", scene_id=scene.id)
    assert scene.settings["gamma"] == "gamma_2_2"


async def test_capture_needs_something_to_capture(
    hass: HomeAssistant, coordinator: ValerionCoordinator
) -> None:
    coordinator.async_set_updated_data(
        ProjectorData(power=coordinator.data.power, values={"POWR": "1"})
    )
    with pytest.raises(InvalidSceneSettingsError) as err:
        await coordinator.scenes.async_save("Nothing")
    assert err.value.translation_key == "scene_empty"


async def test_save_explicit_settings(
    hass: HomeAssistant, coordinator: ValerionCoordinator
) -> None:
    scene = await coordinator.scenes.async_save("Everything", settings=EVERYTHING)
    # Stored in the order they are sent: picture mode first.
    assert list(scene.settings) == [
        "picture_mode",
        "laser_level",
        "aspect_ratio",
        "gamma",
        "dynamic_tone_mapping",
        "color_temperature",
        "enhanced_black_level",
        "motion_enhancement",
    ]
    assert scene.settings == EVERYTHING


@pytest.mark.parametrize(
    ("settings", "key"),
    [
        ({"brightness": 5}, "unknown_scene_setting"),
        ({"laser_level": 11}, "invalid_scene_setting"),
        ({"laser_level": "5"}, "invalid_scene_setting"),
        ({"laser_level": True}, "invalid_scene_setting"),
        ({"gamma": "smpte2084"}, "invalid_scene_setting"),
        ({"gamma": 1}, "invalid_scene_setting"),
        ({"motion_enhancement": "turbo"}, "invalid_scene_setting"),
        ({"picture_mode": ""}, "invalid_scene_setting"),
        ({"picture_mode": 3}, "invalid_scene_setting"),
        ({}, "scene_empty"),
    ],
)
async def test_invalid_settings_rejected(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    coordinator: ValerionCoordinator,
    settings: dict[str, Any],
    key: str,
) -> None:
    with pytest.raises(InvalidSceneSettingsError) as err:
        await coordinator.scenes.async_save("Bad", settings=settings)
    assert err.value.translation_key == key
    assert coordinator.scenes.scenes == []
    assert STORE_KEY not in hass_storage


async def test_names(hass: HomeAssistant, coordinator: ValerionCoordinator) -> None:
    scenes = coordinator.scenes
    scene = await scenes.async_save("Movie night", settings={"laser_level": 5})
    for name, key in (
        ("   ", "scene_name_invalid"),
        ("x" * 101, "scene_name_invalid"),
        ("movie NIGHT", "scene_name_taken"),
    ):
        with pytest.raises(InvalidSceneNameError) as err:
            await scenes.async_save(name, settings={"laser_level": 5})
        assert err.value.translation_key == key
    # A scene keeps its own name when it is updated.
    await scenes.async_save("Movie Night", scene_id=scene.id, settings={"laser_level": 6})
    assert [s.name for s in scenes.scenes] == ["Movie Night"]


async def test_update_and_rename(hass: HomeAssistant, coordinator: ValerionCoordinator) -> None:
    scenes = coordinator.scenes
    scene = await scenes.async_save("Movie night", settings={"laser_level": 5})
    await hass.async_block_till_done()
    entity_id = _scene_entity_id(hass, scene.id)

    updated = await scenes.async_save(
        "Late film", scene_id=scene.id, settings={"laser_level": 2, "gamma": "bt1886"}
    )
    await hass.async_block_till_done()

    assert updated.id == scene.id
    assert updated.settings == {"laser_level": 2, "gamma": "bt1886"}
    assert scenes.get(scene.id) == updated
    # Same entity, new name; the entity ID stays.
    assert _scene_entity_id(hass, scene.id) == entity_id
    assert hass.states.get(entity_id).attributes[ATTR_FRIENDLY_NAME] == "Living room Late film"
    assert er.async_get(hass).async_get(entity_id).original_name == "Late film"
    assert len(hass.states.async_entity_ids(SCENE_DOMAIN)) == 1

    # Updating without a new name keeps the entity as it is.
    await scenes.async_save("Late film", scene_id=scene.id, settings={"laser_level": 4})
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes[ATTR_FRIENDLY_NAME] == "Living room Late film"


async def test_unknown_scene(hass: HomeAssistant, coordinator: ValerionCoordinator) -> None:
    scenes = coordinator.scenes
    with pytest.raises(SceneNotFoundError) as err:
        await scenes.async_save("Ghost", scene_id="nope", settings={"laser_level": 5})
    assert err.value.translation_placeholders == {"scene_id": "nope"}
    with pytest.raises(SceneNotFoundError):
        await scenes.async_delete("nope")
    with pytest.raises(SceneNotFoundError):
        await scenes.async_apply("nope")
    assert scenes.scenes == []


async def test_delete_removes_entity_and_registry_entry(
    hass: HomeAssistant, hass_storage: dict[str, Any], coordinator: ValerionCoordinator
) -> None:
    scenes = coordinator.scenes
    keep = await scenes.async_save("Keep", settings={"laser_level": 5})
    scene = await scenes.async_save("Movie night", settings={"laser_level": 5})
    await hass.async_block_till_done()
    entity_id = _scene_entity_id(hass, scene.id)
    assert hass.states.get(entity_id) is not None

    await scenes.async_delete(scene.id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is None
    assert _scene_entity_id(hass, scene.id) is None
    assert _scene_entity_id(hass, keep.id) is not None
    assert [s["id"] for s in hass_storage[STORE_KEY]["data"]["scenes"]] == [keep.id]


async def test_store_survives_a_reload(
    hass: HomeAssistant, coordinator: ValerionCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    scene = await coordinator.scenes.async_save("Movie night", settings=EVERYTHING)
    await hass.async_block_till_done()
    entity_id = _scene_entity_id(hass, scene.id)

    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    reloaded = mock_config_entry.runtime_data.scenes
    assert reloaded is not coordinator.scenes
    assert reloaded.scenes == [scene]
    assert hass.states.get(entity_id) is not None
    assert _scene_entity_id(hass, scene.id) == entity_id


async def test_orphaned_scene_entity_removed_at_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
) -> None:
    mock_config_entry.add_to_hass(hass)
    orphan = entity_registry.async_get_or_create(
        SCENE_DOMAIN,
        DOMAIN,
        f"{PROJECTOR_MAC}_scene_gone",
        config_entry=mock_config_entry,
    )
    await setup_entry(hass, mock_config_entry)
    assert entity_registry.async_get(orphan.entity_id) is None
    # Other entities of the projector stay.
    assert er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)


async def test_apply_sets_picture_mode_first(
    hass: HomeAssistant,
    projector: FakeProjector,
    coordinator: ValerionCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    scene = await coordinator.scenes.async_save("Everything", settings=EVERYTHING)
    await hass.async_block_till_done()
    projector.received.clear()

    with caplog.at_level(logging.INFO, logger="custom_components.valerion.scene"):
        await _activate(hass, _scene_entity_id(hass, scene.id))

    assert _sets(projector) == [
        "%3PICT HDR Vivid",
        "%3LASL 3",
        "%3ASPR 4",
        # Gamma is locked in HDR10: not sent.
        "%3DYTM 2",
        "%3CLTP 3",
        "%3ENBL 3",
        "%3MOTN 5",
    ]
    assert "scene.living_room_everything skipped gamma (locked)" in caplog.text
    state = hass.states.get(_scene_entity_id(hass, scene.id))
    assert state.state != STATE_UNKNOWN  # time of the last activation
    assert coordinator.data.value(protocol.PICTURE_MODE) == "HDR Vivid"


async def test_apply_reports_locked_and_refused_settings(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # The active mode is not sent again (it returns ERR4 on the projector).
    projector.refused["%3ENBL"] = "ERR3"
    projector.refused["%3MOTN"] = "ERR2"
    scenes = coordinator.scenes
    scene = await scenes.async_save(
        "Theater",
        settings={
            "picture_mode": "HDR Theater",
            "gamma": "gamma_2_2",
            "enhanced_black_level": "high",
            "motion_enhancement": "film",
            "laser_level": 4,
        },
    )
    projector.received.clear()

    result = await scenes.async_apply(scene.id)

    assert result.applied == ["picture_mode", "laser_level"]
    assert result.skipped == [
        SkippedSetting("gamma", "locked"),
        SkippedSetting("enhanced_black_level", "refused"),
        SkippedSetting("motion_enhancement", "refused"),
    ]
    assert result.as_dict() == {
        "applied": ["picture_mode", "laser_level"],
        "skipped": [
            {"setting": "gamma", "reason": "locked"},
            {"setting": "enhanced_black_level", "reason": "refused"},
            {"setting": "motion_enhancement", "reason": "refused"},
        ],
    }
    assert _sets(projector) == ["%3LASL 4", "%3ENBL 3", "%3MOTN 2"]

    # The ERR3 was learned, so the next time it is skipped as locked.
    projector.received.clear()
    result = await scenes.async_apply(scene.id)
    assert SkippedSetting("enhanced_black_level", "locked") in result.skipped
    assert _sets(projector) == ["%3LASL 4", "%3MOTN 2"]


async def test_picture_mode_not_offered_skips_the_rest(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    # An SDR mode while an HDR10 film plays.
    scene = await coordinator.scenes.async_save(
        "Daylight", settings={"picture_mode": "Vivid", "laser_level": 9, "gamma": "gamma_2_2"}
    )
    projector.received.clear()

    result = await coordinator.scenes.async_apply(scene.id)

    assert result.applied == []
    assert result.skipped == [
        SkippedSetting("picture_mode", "not_offered"),
        SkippedSetting("laser_level", "picture_mode_not_set"),
        SkippedSetting("gamma", "picture_mode_not_set"),
    ]
    assert _sets(projector) == []


async def test_refused_picture_mode_skips_the_rest(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    projector.refused["%3PICT"] = "ERR2"
    scene = await coordinator.scenes.async_save(
        "Vivid", settings={"picture_mode": "HDR Vivid", "laser_level": 9}
    )
    projector.received.clear()

    result = await coordinator.scenes.async_apply(scene.id)

    assert result.skipped == [
        SkippedSetting("picture_mode", "refused"),
        SkippedSetting("laser_level", "picture_mode_not_set"),
    ]
    assert _sets(projector) == ["%3PICT HDR Vivid"]


async def test_stored_value_that_cannot_be_set_is_skipped(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    projector: FakeProjector,
    mock_config_entry: MockConfigEntry,
) -> None:
    # Written by an older version or by hand: SMPTE 2084 cannot be chosen.
    hass_storage[STORE_KEY] = {
        "version": 1,
        "key": STORE_KEY,
        "data": {
            "scenes": [
                {"id": "old", "name": "Old", "settings": {"gamma": "smpte2084", "laser_level": 6}}
            ]
        },
    }
    await setup_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert _scene_entity_id(hass, "old") == "scene.living_room_old"
    projector.received.clear()

    result = await coordinator.scenes.async_apply("old")

    assert result.applied == ["laser_level"]
    assert result.skipped == [SkippedSetting("gamma", "not_settable")]
    assert _sets(projector) == ["%3LASL 6"]


async def test_projector_off(
    hass: HomeAssistant, projector: FakeProjector, coordinator: ValerionCoordinator
) -> None:
    scene = await coordinator.scenes.async_save("Movie night", settings={"laser_level": 5})
    await hass.async_block_till_done()
    entity_id = _scene_entity_id(hass, scene.id)
    await _switch_off(hass, projector, coordinator)
    projector.received.clear()

    # The scene stays available, so activating it says why nothing happens.
    with pytest.raises(ProjectorOffError) as err:
        await _activate(hass, entity_id)
    assert err.value.translation_key == "scene_projector_off"
    assert _sets(projector) == []
    with pytest.raises(ProjectorOffError):
        await coordinator.scenes.async_save("Captured while off")
    # Explicit settings can be saved while the projector is off.
    await coordinator.scenes.async_save("Written while off", settings={"laser_level": 2})


async def test_lost_connection_stops_the_scene(
    hass: HomeAssistant, coordinator: ValerionCoordinator
) -> None:
    scene = await coordinator.scenes.async_save(
        "Movie night", settings={"laser_level": 5, "gamma": "gamma_2_2"}
    )
    with (
        patch.object(coordinator, "async_send", side_effect=HomeAssistantError("gone")),
        pytest.raises(HomeAssistantError, match="gone"),
    ):
        await coordinator.scenes.async_apply(scene.id)


async def test_store_removed_with_the_entry(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    coordinator: ValerionCoordinator,
    mock_config_entry: MockConfigEntry,
) -> None:
    await coordinator.scenes.async_save("Movie night", settings={"laser_level": 5})
    assert STORE_KEY in hass_storage

    assert await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert STORE_KEY not in hass_storage
