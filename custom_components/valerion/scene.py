"""Scene entities for the Valerion integration: one per stored picture scene.

The scenes themselves live in ``scenes.py``. Entities are added when a scene
is saved and removed when it is deleted, without reloading the projector.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.scene import Scene
from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .entity import ValerionEntity
from .scenes import SceneChange

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import ValerionConfigEntry, ValerionCoordinator
    from .scenes import PictureScene

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValerionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one scene entity per stored scene, and add new ones as they are saved."""
    coordinator = entry.runtime_data
    scenes = coordinator.scenes

    # Registry entries of scenes that are no longer stored (deleted while the
    # entity was not loaded) would stay behind as orphans.
    registry = er.async_get(hass)
    wanted = {scenes.unique_id(scene.id) for scene in scenes.scenes}
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            registry_entry.domain == Platform.SCENE
            and registry_entry.platform == DOMAIN
            and registry_entry.unique_id not in wanted
        ):
            registry.async_remove(registry_entry.entity_id)

    async_add_entities(ValerionSceneEntity(coordinator, scene) for scene in scenes.scenes)

    @callback
    def scene_changed(change: SceneChange, scene: PictureScene) -> None:
        if change is SceneChange.CREATED:
            async_add_entities([ValerionSceneEntity(coordinator, scene)])

    entry.async_on_unload(scenes.async_add_listener(scene_changed))


class ValerionSceneEntity(ValerionEntity, Scene):
    """A stored picture scene; activating it applies the settings to the projector."""

    def __init__(self, coordinator: ValerionCoordinator, scene: PictureScene) -> None:
        """Initialize the scene entity."""
        super().__init__(coordinator)
        self.scene_id = scene.id
        self._attr_unique_id = coordinator.scenes.unique_id(scene.id)
        self._attr_name = scene.name

    @property
    def available(self) -> bool:
        """Stay available while the projector is off, so activating it explains why it failed."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self) -> None:
        """Follow renames of the stored scene."""
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.scenes.async_add_listener(self._scene_changed))

    @callback
    def _scene_changed(self, change: SceneChange, scene: PictureScene) -> None:
        if change is not SceneChange.UPDATED or scene.id != self.scene_id:
            return
        if scene.name != self._attr_name:
            self._attr_name = scene.name
            # The registry keeps the name the entity was created with.
            er.async_get(self.hass).async_update_entity(self.entity_id, original_name=scene.name)
        self.async_write_ha_state()

    async def async_activate(self, **kwargs: Any) -> None:  # noqa: ARG002 - HA API
        """Apply the scene's settings, picture mode first."""
        result = await self.coordinator.scenes.async_apply(self.scene_id)
        if result.skipped:
            _LOGGER.info(
                "%s skipped %s",
                self.entity_id,
                ", ".join(f"{s.setting} ({s.reason})" for s in result.skipped),
            )
