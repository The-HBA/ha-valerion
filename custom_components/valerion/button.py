"""Button entities for the Valerion integration.

The lens-shift, zoom and focus menus get a button each. The navigation keys
are also buttons, for dashboards; they cost nothing until pressed, so they
are enabled by default (until v0.0.10 they were disabled; the config entry
migration in ``__init__.py`` switches those back on). A last, disabled
button forgets the learned locks, in case a setting was learned as locked
by mistake.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory

from .const import NAVIGATION_KEYS
from .entity import ValerionEntity
from .lib import key_press

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import ValerionConfigEntry, ValerionCoordinator

PARALLEL_UPDATES = 1

_LENS_MENUS = ("lens_shift", "zoom", "focus")

#: The description key is the key name in ``lib.keys.KEYS``.
BUTTONS: tuple[ButtonEntityDescription, ...] = (
    *(
        ButtonEntityDescription(
            key=name,
            translation_key=f"{name}_menu",
            entity_category=EntityCategory.CONFIG,
        )
        for name in _LENS_MENUS
    ),
    *(ButtonEntityDescription(key=name, translation_key=f"key_{name}") for name in NAVIGATION_KEYS),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValerionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons for a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(ValerionButton(coordinator, description) for description in BUTTONS),
            ValerionForgetLocksButton(coordinator),
        ]
    )


class ValerionButton(ValerionEntity, ButtonEntity):
    """One key press or lens menu."""

    def __init__(
        self, coordinator: ValerionCoordinator, description: ButtonEntityDescription
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_button_{description.key}"
        self._press = key_press(description.key)

    async def async_press(self) -> None:
        """Send the key press."""
        await self.coordinator.async_press_keys([self._press], delay=0)
        await self.coordinator.async_request_refresh()


class ValerionForgetLocksButton(ValerionEntity, ButtonEntity):
    """Forget the settings learned as locked (stored in Home Assistant)."""

    _attr_translation_key = "forget_learned_locks"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: ValerionCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device_id}_forget_learned_locks"

    @property
    def available(self) -> bool:
        """Always available: the locks live in Home Assistant, not on the projector."""
        return True

    async def async_press(self) -> None:
        """Forget the learned locks."""
        await self.coordinator.async_forget_locks()
