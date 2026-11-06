"""Websocket commands for the remote card.

Every command names the projector by its config entry ID (``entry_id``) or
its device ID (``device_id``). Errors carry a ``code`` the card can act on:
``projector_not_found``, ``scene_not_found``, ``invalid_settings``,
``invalid_name`` and ``projector_off``. Writes need an administrator.

``valerion/card_info`` gives the card what it shows on its Settings tab:
versions and setup hints. It holds no secrets and no network address.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.loader import async_get_integration
import probatio

from .const import CONF_SECURITY_CODE, CONF_STATUS_NOTIFICATIONS, DOMAIN, NAME
from .lib import protocol
from .scenes import SceneError

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import ValerionConfigEntry
    from .scenes import PictureScene, ValerionScenes

type _Handler = Callable[
    [HomeAssistant, websocket_api.ActiveConnection, dict[str, Any]], Awaitable[None]
]

ATTR_ENTRY_ID: Final = "entry_id"
ATTR_DEVICE_ID: Final = "device_id"
ATTR_SCENE_ID: Final = "scene_id"
ATTR_NAME: Final = "name"
ATTR_SETTINGS: Final = "settings"

#: Error code when no loaded projector matches ``entry_id`` or ``device_id``.
ERR_PROJECTOR_NOT_FOUND: Final = "projector_not_found"

_TARGET: Final = {
    probatio.Exclusive(ATTR_ENTRY_ID, "projector"): str,
    probatio.Exclusive(ATTR_DEVICE_ID, "projector"): str,
}


def _command(command: str, fields: dict[Any, Any] | None = None) -> probatio.All:
    """Return a command schema that needs ``entry_id`` or ``device_id``."""
    return probatio.All(
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
            {probatio.Required("type"): command, **_TARGET, **(fields or {})}
        ),
        cv.has_at_least_one_key(ATTR_ENTRY_ID, ATTR_DEVICE_ID),
    )


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    """Register the integration's websocket commands (once, in ``async_setup``)."""
    websocket_api.async_register_command(hass, ws_list_scenes)
    websocket_api.async_register_command(hass, ws_save_scene)
    websocket_api.async_register_command(hass, ws_delete_scene)
    websocket_api.async_register_command(hass, ws_apply_scene)
    websocket_api.async_register_command(hass, ws_card_info)


class ProjectorNotFoundError(SceneError):
    """No loaded Valerion projector matches the message."""

    code = ERR_PROJECTOR_NOT_FOUND


def _entry(hass: HomeAssistant, msg: dict[str, Any]) -> ValerionConfigEntry:
    """Return the loaded config entry the message names."""
    entry_id: str | None = msg.get(ATTR_ENTRY_ID)
    if (device_id := msg.get(ATTR_DEVICE_ID)) is not None:
        device = dr.async_get(hass).async_get(device_id)
        entry_ids = device.config_entries if device else set()
        entry_id = next(
            (
                candidate
                for candidate in entry_ids
                if (found := hass.config_entries.async_get_entry(candidate))
                and found.domain == DOMAIN
            ),
            None,
        )
    entry = hass.config_entries.async_get_entry(entry_id) if entry_id else None
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        raise ProjectorNotFoundError("projector_not_found")
    return entry


def _scenes(hass: HomeAssistant, msg: dict[str, Any]) -> ValerionScenes:
    return _entry(hass, msg).runtime_data.scenes


def _scene_errors(func: _Handler) -> _Handler:
    """Send a scene error with its own code instead of a generic one."""

    @wraps(func)
    async def wrapper(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
    ) -> None:
        try:
            await func(hass, connection, msg)
        except SceneError as err:
            connection.send_error(
                msg["id"],
                err.code,
                str(err),
                translation_domain=err.translation_domain,
                translation_key=err.translation_key,
                translation_placeholders=err.translation_placeholders,
            )

    return wrapper


def _scene_dict(scenes: ValerionScenes, scene: PictureScene) -> dict[str, Any]:
    return {**scene.as_dict(), "entity_id": scenes.entity_id(scene.id)}


@websocket_api.websocket_command(_command("valerion/scenes/list"))
@websocket_api.async_response
@_scene_errors
async def ws_list_scenes(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the projector's scenes."""
    entry = _entry(hass, msg)
    scenes = entry.runtime_data.scenes
    connection.send_result(
        msg["id"],
        {
            "entry_id": entry.entry_id,
            "scenes": [_scene_dict(scenes, scene) for scene in scenes.scenes],
        },
    )


@websocket_api.websocket_command(
    _command(
        "valerion/scenes/save",
        {
            probatio.Required(ATTR_NAME): str,
            probatio.Optional(ATTR_SCENE_ID): str,
            probatio.Optional(ATTR_SETTINGS): dict,
        },
    )
)
@websocket_api.require_admin
@websocket_api.async_response
@_scene_errors
async def ws_save_scene(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create a scene, or update the one named by ``scene_id``.

    Without ``settings`` the projector's current picture settings are captured.
    """
    scenes = _scenes(hass, msg)
    scene = await scenes.async_save(
        msg[ATTR_NAME], scene_id=msg.get(ATTR_SCENE_ID), settings=msg.get(ATTR_SETTINGS)
    )
    connection.send_result(msg["id"], {"scene": _scene_dict(scenes, scene)})


@websocket_api.websocket_command(
    _command("valerion/scenes/delete", {probatio.Required(ATTR_SCENE_ID): str})
)
@websocket_api.require_admin
@websocket_api.async_response
@_scene_errors
async def ws_delete_scene(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a scene and its entity."""
    await _scenes(hass, msg).async_delete(msg[ATTR_SCENE_ID])
    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    _command("valerion/scenes/apply", {probatio.Required(ATTR_SCENE_ID): str})
)
@websocket_api.async_response
@_scene_errors
async def ws_apply_scene(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Apply a scene; the result lists the settings applied and skipped."""
    result = await _scenes(hass, msg).async_apply(msg[ATTR_SCENE_ID])
    connection.send_result(msg["id"], result.as_dict())


#: Names of the lens menus the card shows, by command code.
_MENU_NAMES: Final = {
    protocol.LENS_SHIFT_MENU.code: "lens_shift",
    protocol.ZOOM_MENU.code: "zoom",
    protocol.FOCUS_MENU.code: "focus",
}


@websocket_api.websocket_command(_command("valerion/card_info"))
@websocket_api.async_response
@_scene_errors
async def ws_card_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return versions and setup hints for the card's Settings tab.

    Only yes or no for the MAC addresses and the security code, never the
    values, and no host: any logged-in user may ask.
    """
    entry = _entry(hass, msg)
    coordinator = entry.runtime_data
    identity = coordinator.data.identity
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, coordinator.device_id)})
    # The device registry keeps the last model and firmware across restarts,
    # for a projector that has not answered since.
    registry_model = device.model if device and device.model != NAME else None
    integration = await async_get_integration(hass, DOMAIN)
    connection.send_result(
        msg["id"],
        {
            "entry_id": entry.entry_id,
            "version": str(integration.version) if integration.version else None,
            "model": identity.model or registry_model,
            "firmware": identity.firmware or (device.sw_version if device else None),
            "setup": {
                "wake_on_lan": bool(coordinator.macs),
                "security_code": bool(entry.data.get(CONF_SECURITY_CODE)),
                "status_notifications": bool(entry.options.get(CONF_STATUS_NOTIFICATIONS)),
                "notifications_listening": coordinator.notifications_listening,
                "unsupported_menus": sorted(
                    _MENU_NAMES[code]
                    for code in coordinator.data.unsupported
                    if code in _MENU_NAMES
                ),
            },
        },
    )
