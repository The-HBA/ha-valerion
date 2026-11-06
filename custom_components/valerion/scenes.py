"""Picture scenes stored in the integration.

A scene is a named set of picture settings (picture mode, laser level,
aspect ratio and the coded settings of ``select.py``). Scenes are stored per
projector with Home Assistant's ``Store`` (``.storage/valerion.<entry id>.scenes``),
so they work from automations, voice and any dashboard, and the remote card
edits them through ``websocket.py``.

Applying a scene sets the picture mode first: the projector keeps the other
settings per picture mode and signal format, so they must go to the right
mode. Settings locked for the current signal, and values that cannot be
chosen, are skipped and reported instead of failing the whole scene.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final

from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.util.ulid import ulid_now

from .const import DOMAIN
from .lib import LASER_LEVEL_MAX, LASER_LEVEL_MIN, AwolLinkCommandError, protocol
from .select import SETTINGS

if TYPE_CHECKING:
    from collections.abc import Callable

    from .coordinator import ProjectorData, ValerionCoordinator
    from .lib import Command

#: Version of the stored scenes (``.storage/valerion.<entry id>.scenes``).
SCENE_STORE_VERSION: Final = 1
#: Longest scene name accepted.
MAX_NAME_LENGTH: Final = 100

#: Why a setting of a scene was not sent.
SKIP_LOCKED: Final = "locked"  # locked for the current signal format and mode
SKIP_NOT_SETTABLE: Final = "not_settable"  # the value cannot be chosen (read-only gamma)
SKIP_NOT_OFFERED: Final = "not_offered"  # picture mode not offered for this signal
SKIP_REFUSED: Final = "refused"  # the projector refused the command
SKIP_NO_PICTURE_MODE: Final = "picture_mode_not_set"  # the scene's mode could not be set

type SceneValue = str | int


class SceneChange(StrEnum):
    """What happened to a scene, for listeners."""

    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"


@dataclass(frozen=True)
class _Setting:
    """One picture setting a scene can hold, with the option keys it accepts."""

    key: str
    command: Command
    #: Option key -> value sent to the projector. Empty for free text (picture mode).
    options: dict[str, SceneValue] = field(default_factory=dict)
    #: Coded values the projector may report, for capturing (enum class).
    values: type[StrEnum] | None = None

    def value_for(self, option: SceneValue) -> SceneValue | None:
        """Return the value to send for ``option``, or None if it cannot be chosen."""
        if self.command is protocol.PICTURE_MODE:
            return option if isinstance(option, str) and option else None
        if self.command is protocol.LASER_LEVEL:
            valid = isinstance(option, int) and not isinstance(option, bool)
            return option if valid and LASER_LEVEL_MIN <= option <= LASER_LEVEL_MAX else None
        return self.options.get(option) if isinstance(option, str) else None

    def option_for(self, raw: str) -> SceneValue | None:
        """Return the option key for a value the projector reported, if it can be set."""
        if self.command is protocol.PICTURE_MODE:
            return raw or None
        if self.command is protocol.LASER_LEVEL:
            try:
                level = int(raw)
            except ValueError:
                return None
            return level if self.value_for(level) is not None else None
        assert self.values is not None  # noqa: S101
        try:
            option = _option(self.values(raw))
        except ValueError:
            return None
        return option if option in self.options else None


def _option(value: StrEnum) -> str:
    """Return the option key for an enum member, the same key as ``select.py``."""
    return value.name.lower()


#: The settings a scene can hold, in the order they are sent. Picture mode
#: comes first because the others belong to the active mode.
SCENE_SETTINGS: Final[tuple[_Setting, ...]] = (
    _Setting("picture_mode", protocol.PICTURE_MODE),
    _Setting("laser_level", protocol.LASER_LEVEL),
    *(
        _Setting(
            description.key,
            description.command,
            options={
                _option(value): value
                for value in (description.settable or tuple(description.values))
            },
            values=description.values,
        )
        for description in SETTINGS
    ),
)
_BY_KEY: Final = {setting.key: setting for setting in SCENE_SETTINGS}


# ------------------------------------------------------------------ errors
class SceneError(HomeAssistantError):
    """A scene request that cannot be carried out; ``code`` names the reason."""

    code = "scene_error"

    def __init__(self, translation_key: str, **placeholders: str) -> None:
        """Create a translated error."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=placeholders or None,
        )


class SceneNotFoundError(SceneError, ServiceValidationError):
    """No scene with this ID."""

    code = "scene_not_found"


class InvalidSceneSettingsError(SceneError, ServiceValidationError):
    """A setting name or value is not valid, or nothing is left to store."""

    code = "invalid_settings"


class InvalidSceneNameError(SceneError, ServiceValidationError):
    """The name is empty, too long or already used by another scene."""

    code = "invalid_name"


class ProjectorOffError(SceneError, ServiceValidationError):
    """The projector is not on, so settings can be neither read nor set (as in ``remote.py``)."""

    code = "projector_off"


# ------------------------------------------------------------------ data
@dataclass(frozen=True)
class PictureScene:
    """A stored scene."""

    id: str
    name: str
    settings: dict[str, SceneValue]

    def as_dict(self) -> dict[str, Any]:
        """Return the scene as stored and as sent to the card."""
        return {"id": self.id, "name": self.name, "settings": dict(self.settings)}


@dataclass(frozen=True)
class SkippedSetting:
    """A scene setting that was not applied, and why."""

    setting: str
    reason: str


@dataclass
class ApplyResult:
    """What applying a scene did."""

    applied: list[str] = field(default_factory=list)
    skipped: list[SkippedSetting] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Return the result for the card."""
        return {
            "applied": list(self.applied),
            "skipped": [{"setting": s.setting, "reason": s.reason} for s in self.skipped],
        }


def scene_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """Return the storage file that keeps the scenes of one projector."""
    return Store(hass, SCENE_STORE_VERSION, f"{DOMAIN}.{entry_id}.scenes")


def scene_unique_id(device_id: str, scene_id: str) -> str:
    """Return the unique ID of a scene's entity."""
    return f"{device_id}_scene_{scene_id}"


def validate_settings(settings: dict[str, Any]) -> dict[str, SceneValue]:
    """Return ``settings`` in the fixed order, or raise if a name or value is invalid."""
    for key, option in settings.items():
        setting = _BY_KEY.get(key)
        if setting is None:
            raise InvalidSceneSettingsError("unknown_scene_setting", setting=str(key))
        if setting.value_for(option) is None:
            raise InvalidSceneSettingsError("invalid_scene_setting", setting=key, value=str(option))
    if not settings:
        raise InvalidSceneSettingsError("scene_empty")
    return {s.key: settings[s.key] for s in SCENE_SETTINGS if s.key in settings}


def capture_settings(data: ProjectorData | None) -> dict[str, SceneValue]:
    """Return the current picture settings, without unknown, locked or read-only ones."""
    if data is None or not data.is_on:
        raise ProjectorOffError("scene_projector_off")
    settings: dict[str, SceneValue] = {}
    for setting in SCENE_SETTINGS:
        raw = data.value(setting.command)
        if raw is None or data.is_locked(setting.command):
            continue
        option = setting.option_for(raw)
        if option is not None:
            settings[setting.key] = option
    if not settings:
        raise InvalidSceneSettingsError("scene_empty")
    return settings


class ValerionScenes:
    """The scenes of one projector: stored, edited and applied."""

    def __init__(self, hass: HomeAssistant, coordinator: ValerionCoordinator) -> None:
        """Initialize; call ``async_load`` before use."""
        self.hass = hass
        self.coordinator = coordinator
        self._store = scene_store(hass, coordinator.config_entry.entry_id)
        self._scenes: dict[str, PictureScene] = {}
        self._listeners: list[Callable[[SceneChange, PictureScene], None]] = []

    async def async_load(self) -> None:
        """Load the stored scenes."""
        stored = await self._store.async_load() or {}
        self._scenes = {
            item["id"]: PictureScene(item["id"], item["name"], dict(item.get("settings", {})))
            for item in stored.get("scenes", [])
        }

    @property
    def scenes(self) -> list[PictureScene]:
        """Return the scenes in the order they were created."""
        return list(self._scenes.values())

    def get(self, scene_id: str) -> PictureScene:
        """Return one scene, or raise if there is none with this ID."""
        if (scene := self._scenes.get(scene_id)) is None:
            raise SceneNotFoundError("scene_not_found", scene_id=scene_id)
        return scene

    def unique_id(self, scene_id: str) -> str:
        """Return the unique ID of the entity of ``scene_id``."""
        return scene_unique_id(self.coordinator.device_id, scene_id)

    def entity_id(self, scene_id: str) -> str | None:
        """Return the entity ID of a scene, if its entity is registered."""
        return er.async_get(self.hass).async_get_entity_id(
            Platform.SCENE, DOMAIN, self.unique_id(scene_id)
        )

    @callback
    def async_add_listener(
        self, listener: Callable[[SceneChange, PictureScene], None]
    ) -> CALLBACK_TYPE:
        """Call ``listener`` after every change; return a function that stops it."""
        self._listeners.append(listener)

        @callback
        def remove() -> None:
            self._listeners.remove(listener)

        return remove

    async def async_save(
        self,
        name: str,
        *,
        scene_id: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> PictureScene:
        """Create a scene, or update ``scene_id``.

        Without ``settings`` the current values are captured from the
        projector, leaving out settings that are unknown or locked.
        """
        if scene_id is not None:
            self.get(scene_id)
        name = self._check_name(name, scene_id)
        values = (
            capture_settings(self.coordinator.data)
            if settings is None
            else validate_settings(settings)
        )
        change = SceneChange.CREATED if scene_id is None else SceneChange.UPDATED
        if scene_id is None:
            scene_id = ulid_now().lower()
        scene = PictureScene(scene_id, name, values)
        self._scenes[scene_id] = scene
        await self._async_save()
        self._notify(change, scene)
        return scene

    def _check_name(self, name: str, scene_id: str | None) -> str:
        name = name.strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            raise InvalidSceneNameError("scene_name_invalid", max=str(MAX_NAME_LENGTH))
        taken = any(
            scene.name.casefold() == name.casefold() and scene.id != scene_id
            for scene in self._scenes.values()
        )
        if taken:
            raise InvalidSceneNameError("scene_name_taken", name=name)
        return name

    async def async_delete(self, scene_id: str) -> None:
        """Delete a scene; its entity disappears from the entity registry too."""
        scene = self.get(scene_id)
        del self._scenes[scene_id]
        await self._async_save()
        if (entity_id := self.entity_id(scene_id)) is not None:
            # Removing the registry entry also removes the running entity.
            er.async_get(self.hass).async_remove(entity_id)
        self._notify(SceneChange.DELETED, scene)

    async def async_apply(self, scene_id: str) -> ApplyResult:
        """Send the scene's settings, picture mode first, and report what was skipped."""
        scene = self.get(scene_id)
        if not self.coordinator.data or not self.coordinator.data.is_on:
            raise ProjectorOffError("scene_projector_off")
        result = ApplyResult()
        mode_missed = False
        for setting in SCENE_SETTINGS:
            if setting.key not in scene.settings:
                continue
            if mode_missed:
                result.skipped.append(SkippedSetting(setting.key, SKIP_NO_PICTURE_MODE))
                continue
            reason = await self._async_apply_one(setting, scene.settings[setting.key])
            if reason is None:
                result.applied.append(setting.key)
                continue
            result.skipped.append(SkippedSetting(setting.key, reason))
            # The other settings belong to the scene's mode; sending them now
            # would change what the projector remembers for another mode.
            mode_missed = setting.command is protocol.PICTURE_MODE
        return result

    async def _async_apply_one(self, setting: _Setting, option: SceneValue) -> str | None:
        """Send one setting; return why it was skipped, or None if it was sent."""
        # Read the data again for every setting: a new picture mode changes the locks.
        data = self.coordinator.data
        value = setting.value_for(option)
        if value is None:
            return SKIP_NOT_SETTABLE
        if data.is_locked(setting.command):
            return SKIP_LOCKED
        try:
            if setting.command is protocol.PICTURE_MODE:
                mode = str(value)
                current = data.value(protocol.PICTURE_MODE)
                if data.picture_modes and mode not in data.picture_modes and mode != current:
                    return SKIP_NOT_OFFERED
                await self.coordinator.async_set_picture_mode(mode)
            else:
                await self.coordinator.async_send(setting.command, value)
        except HomeAssistantError as err:
            # A refused value (ERRx) skips this setting; a lost connection
            # or a wrong security code stops the scene.
            if isinstance(err.__cause__, AwolLinkCommandError):
                return SKIP_REFUSED
            raise
        return None

    async def _async_save(self) -> None:
        await self._store.async_save(
            {"scenes": [scene.as_dict() for scene in self._scenes.values()]}
        )

    def _notify(self, change: SceneChange, scene: PictureScene) -> None:
        for listener in list(self._listeners):
            listener(change, scene)
