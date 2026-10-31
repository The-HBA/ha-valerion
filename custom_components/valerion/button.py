"""Button entities for the Valerion integration.

The lens-shift, zoom and focus menus get a button each. A menu the
projector refuses while on (no motorised lens on that model) is remembered,
and its button becomes unavailable and hidden until *Forget learned locks*
or a firmware update. The navigation keys
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
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

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
            *(
                (ValerionMenuButton if description.key in _LENS_MENUS else ValerionButton)(
                    coordinator, description
                )
                for description in BUTTONS
            ),
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


class ValerionMenuButton(ValerionButton):
    """A lens-shift, zoom or focus menu, hidden when the projector lacks it."""

    @property
    def _unsupported(self) -> bool:
        return self._press.command.code in self.coordinator.data.unsupported

    @property
    def available(self) -> bool:
        """Unavailable once the projector has refused this menu."""
        return super().available and not self._unsupported

    async def async_added_to_hass(self) -> None:
        """Apply what was learned before the last restart."""
        await super().async_added_to_hass()
        self._sync_hidden()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._sync_hidden()
        super()._handle_coordinator_update()

    @callback
    def _sync_hidden(self) -> None:
        """Hide the button while unsupported; never touch one the user hid."""
        entry = self.registry_entry
        if entry is None:
            return
        if self._unsupported and entry.hidden_by is None:
            hidden_by: er.RegistryEntryHider | None = er.RegistryEntryHider.INTEGRATION
        elif not self._unsupported and entry.hidden_by is er.RegistryEntryHider.INTEGRATION:
            hidden_by = None
        else:
            return
        er.async_get(self.hass).async_update_entity(self.entity_id, hidden_by=hidden_by)


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
        """Forget the learned locks and unsupported menus."""
        await self.coordinator.async_forget_locks()
