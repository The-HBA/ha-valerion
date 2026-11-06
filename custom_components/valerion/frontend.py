"""Serve the remote card and register it with the dashboards.

The card is plain JavaScript in ``www/``. Home Assistant serves that folder
under ``URL_BASE``, and the card is added to the dashboards once, however
many projectors are set up:

- Dashboard resources kept in storage (the default): one Lovelace resource
  of type ``module``. Its URL carries ``?v=<version>`` so browsers load the
  new card after an update; an existing resource is updated, not duplicated.
- Dashboard resources kept in YAML: the card is added as an extra frontend
  module instead, because the resources in YAML cannot be changed from here.

The resource is removed again when the last projector is removed.

The same card is also offered full screen as a sidebar page ("Projector"),
one for the whole Home Assistant. It shows while at least one loaded
projector has the option "Show in sidebar" on (the default).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from homeassistant.components import panel_custom
from homeassistant.components.frontend import (
    add_extra_js_url,
    async_remove_panel,
    remove_extra_js_url,
)
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.loader import async_get_integration
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

#: Where Home Assistant serves the files in ``www/``.
URL_BASE = "/valerion_static"
WWW_DIR = Path(__file__).parent / "www"
CARD_FILE = "valerion-card.js"
CARD_PATH = f"{URL_BASE}/{CARD_FILE}"
PANEL_FILE = "valerion-panel.js"
PANEL_PATH = f"{URL_BASE}/{PANEL_FILE}"
#: The sidebar page: /valerion in the browser.
PANEL_URL_PATH = "valerion"
PANEL_ELEMENT = "valerion-panel"
PANEL_TITLE = "Projector"
PANEL_ICON = "mdi:projector"


@dataclass
class FrontendData:
    """What this Home Assistant run has registered so far."""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    static_path_registered: bool = False
    #: The card URL once it is registered, ``None`` before.
    card_url: str | None = None
    #: Set when the card was added as an extra module (YAML resources).
    extra_module_url: str | None = None
    #: Loaded projectors that want the sidebar page.
    panel_entries: set[str] = field(default_factory=set)
    #: The panel module URL while the sidebar page is registered, ``None`` before.
    panel_url: str | None = None


DATA_FRONTEND: HassKey[FrontendData] = HassKey(f"{DOMAIN}_frontend")


def _data(hass: HomeAssistant) -> FrontendData:
    return hass.data.setdefault(DATA_FRONTEND, FrontendData())


def _is_card(url: str) -> bool:
    """Tell whether a resource URL points at this card, whatever its version."""
    return urlsplit(url).path == CARD_PATH


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Serve ``www/`` and register the card. Safe to call for every projector."""
    data = _data(hass)
    async with data.lock:
        if not data.static_path_registered:
            # No cache headers: the files are small, and a reinstall of the
            # same version must still reach the browser.
            await hass.http.async_register_static_paths(
                [StaticPathConfig(URL_BASE, str(WWW_DIR), cache_headers=False)]
            )
            data.static_path_registered = True
        if data.card_url is None:
            integration = await async_get_integration(hass, DOMAIN)
            url = f"{CARD_PATH}?v={integration.version}"
            await _async_register_card(hass, data, url)
            data.card_url = url


async def async_update_panel(hass: HomeAssistant, entry_id: str, *, show: bool) -> None:
    """Note whether a projector wants the sidebar page, then add or remove the page.

    Called with the option's value when a projector is set up, and with
    ``show=False`` when it is unloaded (also before a reload and a removal).
    """
    data = _data(hass)
    async with data.lock:
        if show:
            data.panel_entries.add(entry_id)
        else:
            data.panel_entries.discard(entry_id)
        if data.panel_entries and data.panel_url is None:
            integration = await async_get_integration(hass, DOMAIN)
            url = f"{PANEL_PATH}?v={integration.version}"
            await panel_custom.async_register_panel(
                hass,
                frontend_url_path=PANEL_URL_PATH,
                webcomponent_name=PANEL_ELEMENT,
                sidebar_title=PANEL_TITLE,
                sidebar_icon=PANEL_ICON,
                module_url=url,
                require_admin=False,
            )
            data.panel_url = url
            _LOGGER.debug("Added the sidebar page %s", url)
        elif not data.panel_entries and data.panel_url is not None:
            async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
            data.panel_url = None
            _LOGGER.debug("Removed the sidebar page")


async def _async_register_card(hass: HomeAssistant, data: FrontendData, url: str) -> None:
    lovelace = hass.data[LOVELACE_DATA]
    if lovelace.resource_mode != MODE_STORAGE:
        add_extra_js_url(hass, url)
        data.extra_module_url = url
        return
    resources = lovelace.resources
    # Loads the stored resources if no dashboard has asked for them yet.
    await resources.async_get_info()
    ours = [item for item in resources.async_items() if _is_card(item["url"])]
    if not ours:
        await resources.async_create_item({"res_type": "module", "url": url})
        _LOGGER.debug("Added dashboard resource %s", url)
        return
    first, *duplicates = ours
    if first["url"] != url or first.get("type") != "module":
        await resources.async_update_item(first["id"], {"res_type": "module", "url": url})
        _LOGGER.debug("Updated dashboard resource to %s", url)
    for item in duplicates:
        await resources.async_delete_item(item["id"])


async def async_remove_frontend(hass: HomeAssistant, removed: ConfigEntry) -> None:
    """Remove the card from the dashboards once no projector is left."""
    if any(
        entry.entry_id != removed.entry_id
        for entry in hass.config_entries.async_entries(DOMAIN, include_ignore=False)
    ):
        return
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None:
        return
    data = _data(hass)
    async with data.lock:
        if data.extra_module_url is not None:
            remove_extra_js_url(hass, data.extra_module_url)
            data.extra_module_url = None
        if lovelace.resource_mode == MODE_STORAGE:
            resources = lovelace.resources
            await resources.async_get_info()
            for item in [item for item in resources.async_items() if _is_card(item["url"])]:
                await resources.async_delete_item(item["id"])
                _LOGGER.debug("Removed dashboard resource %s", item["url"])
        data.card_url = None
