"""Tests for serving the remote card and registering it with the dashboards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, DATA_PANELS
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.valerion.const import CONF_SHOW_PANEL, DOMAIN
from custom_components.valerion.frontend import CARD_PATH, DATA_FRONTEND, PANEL_PATH

from .conftest import setup_entry

MANIFEST = Path(__file__).parents[2] / "custom_components" / "valerion" / "manifest.json"
VERSION = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
CARD_URL = f"{CARD_PATH}?v={VERSION}"
PANEL_URL = f"{PANEL_PATH}?v={VERSION}"


def _resources(hass: HomeAssistant) -> list[dict[str, Any]]:
    return list(hass.data[LOVELACE_DATA].resources.async_items())


def _card_resources(hass: HomeAssistant) -> list[dict[str, Any]]:
    return [item for item in _resources(hass) if item["url"].startswith(CARD_PATH)]


def _stored_resources(*urls: str) -> dict[str, Any]:
    return {
        "version": 1,
        "minor_version": 1,
        "key": "lovelace_resources",
        "data": {
            "items": [
                {"id": f"id{index}", "type": "module", "url": url} for index, url in enumerate(urls)
            ]
        },
    }


def _other_entry(entry: MockConfigEntry, options: dict[str, Any] | None = None) -> MockConfigEntry:
    """A second projector (same fake projector, different unique ID)."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Other room",
        unique_id="00:00:5e:00:53:02",
        data=dict(entry.data),
        options=options or {},
        version=1,
        minor_version=2,
    )


def _has_panel(hass: HomeAssistant) -> bool:
    return "valerion" in hass.data.get(DATA_PANELS, {})


async def _set_show_panel(hass: HomeAssistant, entry: MockConfigEntry, *, show: bool) -> None:
    """Switch "Show in sidebar" in the settings dialog, as a user does."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {CONF_SHOW_PANEL: show})
    await hass.async_block_till_done()


async def test_card_files_are_served(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    await setup_entry(hass, mock_config_entry)
    client = await hass_client_no_auth()

    for name, element in (
        ("valerion-card.js", "valerion-card"),
        ("valerion-card-editor.js", "valerion-card-editor"),
        ("valerion-panel.js", "valerion-panel"),
    ):
        response = await client.get(f"/valerion_static/{name}?v={VERSION}")
        assert response.status == 200
        assert f'"{element}"' in await response.text()


async def test_storage_mode_creates_one_resource(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    await setup_entry(hass, mock_config_entry)
    [resource] = _resources(hass)
    assert resource["type"] == "module"
    assert resource["url"] == CARD_URL


async def test_storage_mode_updates_an_old_version_and_drops_duplicates(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, hass_storage: dict[str, Any]
) -> None:
    hass_storage["lovelace_resources"] = _stored_resources(
        "/local/other-card.js",
        f"{CARD_PATH}?v=0.0.1",
        CARD_PATH,
    )
    await setup_entry(hass, mock_config_entry)

    assert _resources(hass) == [
        {"id": "id0", "type": "module", "url": "/local/other-card.js"},
        {"id": "id1", "type": "module", "url": CARD_URL},
    ]


async def test_storage_mode_keeps_a_current_resource(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, hass_storage: dict[str, Any]
) -> None:
    hass_storage["lovelace_resources"] = _stored_resources(CARD_URL)
    await setup_entry(hass, mock_config_entry)
    assert _resources(hass) == [{"id": "id0", "type": "module", "url": CARD_URL}]


async def test_registered_once_for_several_projectors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    other = _other_entry(mock_config_entry)
    await setup_entry(hass, mock_config_entry)
    await setup_entry(hass, other)
    assert [item["url"] for item in _card_resources(hass)] == [CARD_URL]

    # A reload does not touch the resource again.
    first_id = _card_resources(hass)[0]["id"]
    assert await hass.config_entries.async_reload(other.entry_id)
    await hass.async_block_till_done()
    assert [item["id"] for item in _card_resources(hass)] == [first_id]


async def test_resource_removed_with_the_last_projector(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    other = _other_entry(mock_config_entry)
    await setup_entry(hass, mock_config_entry)
    await setup_entry(hass, other)

    await hass.config_entries.async_remove(other.entry_id)
    await hass.async_block_till_done()
    assert [item["url"] for item in _card_resources(hass)] == [CARD_URL]

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert _card_resources(hass) == []
    assert hass.data[DATA_FRONTEND].card_url is None

    # Adding a projector again registers the card again.
    again = _other_entry(mock_config_entry)
    await setup_entry(hass, again)
    assert [item["url"] for item in _card_resources(hass)] == [CARD_URL]


async def test_yaml_mode_adds_an_extra_module(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    assert await async_setup_component(hass, "lovelace", {"lovelace": {"resource_mode": "yaml"}})
    await setup_entry(hass, mock_config_entry)

    assert CARD_URL in hass.data[DATA_EXTRA_MODULE_URL].urls
    assert _resources(hass) == []

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert CARD_URL not in hass.data[DATA_EXTRA_MODULE_URL].urls


async def test_remove_without_dashboards_loaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    # An entry removed before anything was set up in this run.
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert LOVELACE_DATA not in hass.data


async def test_sidebar_page_registered_on_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    await setup_entry(hass, mock_config_entry)

    panel = hass.data[DATA_PANELS]["valerion"].to_response()
    assert panel["component_name"] == "custom"
    assert panel["title"] == "Projector"
    assert panel["icon"] == "mdi:projector"
    assert panel["url_path"] == "valerion"
    assert panel["require_admin"] is False
    assert panel["show_in_sidebar"] is True
    custom = panel["config"]["_panel_custom"]
    assert custom["name"] == "valerion-panel"
    assert custom["module_url"] == PANEL_URL
    assert custom["embed_iframe"] is False
    assert hass.data[DATA_FRONTEND].panel_url == PANEL_URL


async def test_sidebar_page_not_registered_with_the_option_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options={CONF_SHOW_PANEL: False})
    await setup_entry(hass, mock_config_entry)
    assert not _has_panel(hass)


async def test_sidebar_page_follows_the_option(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    await setup_entry(hass, mock_config_entry)
    assert _has_panel(hass)

    await _set_show_panel(hass, mock_config_entry, show=False)
    assert mock_config_entry.options[CONF_SHOW_PANEL] is False
    assert not _has_panel(hass)

    await _set_show_panel(hass, mock_config_entry, show=True)
    assert _has_panel(hass)
    assert hass.data[DATA_PANELS]["valerion"].config["_panel_custom"]["module_url"] == PANEL_URL


async def test_sidebar_page_stays_while_one_projector_shows_it(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    other = _other_entry(mock_config_entry, {CONF_SHOW_PANEL: False})
    await setup_entry(hass, mock_config_entry)
    await setup_entry(hass, other)
    assert _has_panel(hass)
    assert hass.data[DATA_FRONTEND].panel_entries == {mock_config_entry.entry_id}

    # Switching it on for the second projector, then off for the first: still there.
    await _set_show_panel(hass, other, show=True)
    await _set_show_panel(hass, mock_config_entry, show=False)
    assert _has_panel(hass)

    await _set_show_panel(hass, other, show=False)
    assert not _has_panel(hass)


async def test_sidebar_page_removed_with_the_last_projector(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    other = _other_entry(mock_config_entry)
    await setup_entry(hass, mock_config_entry)
    await setup_entry(hass, other)

    await hass.config_entries.async_remove(other.entry_id)
    await hass.async_block_till_done()
    assert _has_panel(hass)

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not _has_panel(hass)
    assert hass.data[DATA_FRONTEND].panel_url is None


async def test_sidebar_page_goes_when_the_projector_is_unloaded(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    await setup_entry(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not _has_panel(hass)

    # A reload brings it back, without an error about a panel already registered.
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert _has_panel(hass)
