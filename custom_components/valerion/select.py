"""Select entities for the Valerion integration.

Picture mode, aspect ratio and the picture settings that have a fixed list
of values. Each setting belongs to the active picture mode, and some are
locked for the current signal (gamma presets in SDR only, dynamic tone
mapping in HDR10 only); a locked setting shows as unavailable, including
one the projector refused earlier for the same signal format and mode.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN
from .entity import ValerionEntity
from .lib import (
    SETTABLE_GAMMA,
    AspectRatio,
    ColorTemperature,
    DynamicToneMapping,
    EnhancedBlackLevel,
    Gamma,
    MotionEnhancement,
    protocol,
)

if TYPE_CHECKING:
    from enum import StrEnum

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import ValerionConfigEntry, ValerionCoordinator
    from .lib import Command

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class ValerionSettingDescription(SelectEntityDescription):
    """A picture setting with coded values.

    The options are the lower-case enum member names (``gamma_2_2``), which
    are translated in ``translations/en.json``. ``settable`` limits what can be
    chosen; other values are only shown while the projector reports them.
    """

    command: Command
    values: type[StrEnum]
    settable: tuple[StrEnum, ...] | None = None


SETTINGS: tuple[ValerionSettingDescription, ...] = (
    # Not in the official list as a set command, but verified on the Pro2 for
    # every value with SDR, HDR10 and Dolby Vision (docs/protocol.md).
    ValerionSettingDescription(
        key="aspect_ratio",
        translation_key="aspect_ratio",
        entity_category=EntityCategory.CONFIG,
        command=protocol.ASPECT_RATIO,
        values=AspectRatio,
    ),
    ValerionSettingDescription(
        key="gamma",
        translation_key="gamma",
        entity_category=EntityCategory.CONFIG,
        command=protocol.GAMMA,
        values=Gamma,
        settable=SETTABLE_GAMMA,
    ),
    ValerionSettingDescription(
        key="dynamic_tone_mapping",
        translation_key="dynamic_tone_mapping",
        entity_category=EntityCategory.CONFIG,
        command=protocol.DYNAMIC_TONE_MAPPING,
        values=DynamicToneMapping,
    ),
    ValerionSettingDescription(
        key="color_temperature",
        translation_key="color_temperature",
        entity_category=EntityCategory.CONFIG,
        command=protocol.COLOR_TEMPERATURE,
        values=ColorTemperature,
    ),
    ValerionSettingDescription(
        key="enhanced_black_level",
        translation_key="enhanced_black_level",
        entity_category=EntityCategory.CONFIG,
        command=protocol.ENHANCED_BLACK_LEVEL,
        values=EnhancedBlackLevel,
    ),
    ValerionSettingDescription(
        key="motion_enhancement",
        translation_key="motion_enhancement",
        entity_category=EntityCategory.CONFIG,
        command=protocol.MOTION_ENHANCEMENT,
        values=MotionEnhancement,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValerionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the selects for a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            ValerionPictureModeSelect(coordinator),
            *(ValerionSettingSelect(coordinator, description) for description in SETTINGS),
        ]
    )


class ValerionPictureModeSelect(ValerionEntity, SelectEntity):
    """The picture mode, from the list the projector offers for the current signal."""

    _attr_translation_key = "picture_mode"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: ValerionCoordinator) -> None:
        """Initialize the select."""
        super().__init__(coordinator, protocol.PICTURE_MODE)
        self._attr_unique_id = f"{self.device_id}_picture_mode"

    @property
    def available(self) -> bool:
        """Unavailable while the projector reports the mode as locked."""
        return super().available and not self.coordinator.data.is_locked(protocol.PICTURE_MODE)

    @property
    def options(self) -> list[str]:
        """Return the modes valid for the current signal (SDR, HDR10, Dolby Vision...)."""
        modes = list(self.coordinator.data.picture_modes)
        current = self.current_option
        if current and current not in modes:
            modes.append(current)
        return modes

    @property
    def current_option(self) -> str | None:
        """Return the active picture mode."""
        return self.coordinator.data.value(protocol.PICTURE_MODE) or None

    async def async_select_option(self, option: str) -> None:
        """Switch to another picture mode."""
        await self.coordinator.async_set_picture_mode(option)


class ValerionSettingSelect(ValerionEntity, SelectEntity):
    """One picture setting with a fixed list of values."""

    entity_description: ValerionSettingDescription

    def __init__(
        self, coordinator: ValerionCoordinator, description: ValerionSettingDescription
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, description.command)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_{description.key}"
        self._settable = description.settable or tuple(description.values)

    @property
    def available(self) -> bool:
        """Unavailable while the setting is locked for the current signal and mode."""
        return super().available and not self.coordinator.data.is_locked(
            self.entity_description.command
        )

    @property
    def options(self) -> list[str]:
        """Return the settable values, plus a read-only value the projector reports."""
        options = [_option(value) for value in self._settable]
        current = self.current_option
        if current and current not in options:
            options.append(current)
        return options

    @property
    def current_option(self) -> str | None:
        """Return the current value as an option key."""
        raw = self.coordinator.data.value(self.entity_description.command)
        if raw is None:
            return None
        try:
            return _option(self.entity_description.values(raw))
        except ValueError:
            _LOGGER.debug("Unknown %s value %r", self.entity_description.command, raw)
            return None

    async def async_select_option(self, option: str) -> None:
        """Send the new value."""
        value = next((v for v in self._settable if _option(v) == option), None)
        if value is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="value_not_settable",
                translation_placeholders={"value": option},
            )
        await self.coordinator.async_send(self.entity_description.command, value)


def _option(value: StrEnum) -> str:
    """Return the option key for an enum member, for example ``gamma_2_2``."""
    return value.name.lower()
