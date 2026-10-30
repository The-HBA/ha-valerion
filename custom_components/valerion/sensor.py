"""Sensor entities for the Valerion integration.

The AWOL Link status sensor records how the projector answered the last poll
(answering, silent, refused, unreachable). Together with the media player's
on / standby / off state, Home Assistant history then shows how deep the
projector sleeps in standby.

The signal sensors decode ``%3SINF`` (video timing, HDR format, audio and
colour details). Fan and temperature sensors are created per slot: the
projector reports a fixed number of slots and fills only those it has, so a
sensor is added the first time its slot reports a value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import REVOLUTIONS_PER_MINUTE, EntityCategory, UnitOfTemperature
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er

from .coordinator import Connection, ProjectorData, ValerionConfigEntry, ValerionCoordinator
from .entity import ValerionEntity
from .lib import (
    AudioFormat,
    ColorDepth,
    ColorFormat,
    ColorPrimaries,
    HdrFormat,
    LedStatus,
    parse_number_list,
    protocol,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from enum import StrEnum

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from homeassistant.helpers.typing import StateType

    from .lib import Command

# Sensors only read the coordinator's data; they never send commands.
PARALLEL_UPDATES = 0

NO_SIGNAL = "no_signal"


def _options(values: type[StrEnum]) -> list[str]:
    return [member.name.lower() for member in values]


def _option(member: StrEnum | None) -> str | None:
    return member.name.lower() if member is not None else None


def _video_signal(data: ProjectorData) -> str | None:
    signal = data.signal
    if signal is None or not signal.has_signal:
        return None
    return str(signal.timing) if signal.timing else signal.video_format


def _hdr_format(data: ProjectorData) -> str | None:
    signal = data.signal
    if signal is None:
        return None
    return _option(signal.hdr) if signal.has_signal else NO_SIGNAL


def _led_status(data: ProjectorData) -> str | None:
    raw = data.value(protocol.LED_STATUS)
    try:
        return _option(LedStatus(raw)) if raw is not None else None
    except ValueError:
        return None


@dataclass(frozen=True, kw_only=True)
class ValerionSensorDescription(SensorEntityDescription):
    """A sensor computed from one polled command."""

    command: Command
    value_fn: Callable[[ProjectorData], StateType]


SENSORS: tuple[ValerionSensorDescription, ...] = (
    ValerionSensorDescription(
        key="video_signal",
        translation_key="video_signal",
        command=protocol.SIGNAL_INFO,
        value_fn=_video_signal,
    ),
    ValerionSensorDescription(
        key="hdr_format",
        translation_key="hdr_format",
        device_class=SensorDeviceClass.ENUM,
        options=[*_options(HdrFormat), NO_SIGNAL],
        command=protocol.SIGNAL_INFO,
        value_fn=_hdr_format,
    ),
    ValerionSensorDescription(
        key="audio_format",
        translation_key="audio_format",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=_options(AudioFormat),
        command=protocol.SIGNAL_INFO,
        value_fn=lambda data: _option(data.signal.audio) if data.signal else None,
    ),
    ValerionSensorDescription(
        key="color_depth",
        translation_key="color_depth",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=_options(ColorDepth),
        command=protocol.SIGNAL_INFO,
        value_fn=lambda data: _option(data.signal.depth) if data.signal else None,
    ),
    ValerionSensorDescription(
        key="color_format",
        translation_key="color_format",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=_options(ColorFormat),
        command=protocol.SIGNAL_INFO,
        value_fn=lambda data: _option(data.signal.chroma) if data.signal else None,
    ),
    ValerionSensorDescription(
        key="color_primaries",
        translation_key="color_primaries",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=_options(ColorPrimaries),
        command=protocol.SIGNAL_INFO,
        value_fn=lambda data: _option(data.signal.primaries) if data.signal else None,
    ),
    ValerionSensorDescription(
        key="led_status",
        translation_key="led_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=_options(LedStatus),
        command=protocol.LED_STATUS,
        value_fn=_led_status,
    ),
)


@dataclass(frozen=True, kw_only=True)
class ValerionSlotDescription(SensorEntityDescription):
    """A multi-slot reading (``%3FANS``, ``%3TEMP``); one sensor per used slot."""

    command: Command


SLOT_SENSORS: tuple[ValerionSlotDescription, ...] = (
    ValerionSlotDescription(
        key="fan",
        translation_key="fan_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        command=protocol.FAN_SPEED,
    ),
    # The unit is not documented; the Pro2 reports 33 to 48, which only
    # makes sense as degrees Celsius.
    ValerionSlotDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        command=protocol.TEMPERATURE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValerionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors for a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            ValerionLinkStatusSensor(coordinator),
            *(ValerionSensor(coordinator, description) for description in SENSORS),
        ]
    )
    for description in SLOT_SENSORS:
        _track_slots(hass, entry, async_add_entities, description)


def _track_slots(
    hass: HomeAssistant,
    entry: ValerionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    description: ValerionSlotDescription,
) -> None:
    """Add a sensor for every slot that reports a value, now or later.

    Slots seen before are in the entity registry, so their sensors come back
    after a restart even while the projector is off.
    """
    coordinator = entry.runtime_data
    prefix = f"{coordinator.device_id}_{description.key}_"
    known: set[int] = set()

    def add(slots: set[int]) -> None:
        known.update(slots)
        async_add_entities(
            ValerionSlotSensor(coordinator, description, slot) for slot in sorted(slots)
        )

    registry = er.async_get(hass)
    registered = {
        int(suffix)
        for reg in er.async_entries_for_config_entry(registry, entry.entry_id)
        if reg.domain == "sensor"
        and (suffix := reg.unique_id.removeprefix(prefix)) != reg.unique_id
        and suffix.isdigit()
    }
    if registered:
        add(registered)

    @callback
    def check_slots() -> None:
        raw = coordinator.data.value(description.command) if coordinator.data else None
        if raw is None:
            return
        used = {index for index, value in enumerate(parse_number_list(raw), start=1) if value}
        if new := used - known:
            add(new)

    check_slots()
    # The listener's context makes the coordinator poll the command even
    # before any slot sensor exists.
    entry.async_on_unload(coordinator.async_add_listener(check_slots, description.command))


class ValerionLinkStatusSensor(ValerionEntity, SensorEntity):
    """How the projector answered the last AWOL Link poll."""

    _attr_translation_key = "link_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: ValerionCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.device_id}_link_status"
        self._attr_options = [state.value for state in Connection]

    @property
    def available(self) -> bool:
        """Stay available in every state; recording silence is the point."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> str:
        """Return the connection state of the last poll."""
        return self.coordinator.data.connection.value


class ValerionSensor(ValerionEntity, SensorEntity):
    """A sensor described by a ``ValerionSensorDescription``."""

    entity_description: ValerionSensorDescription

    def __init__(
        self, coordinator: ValerionCoordinator, description: ValerionSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.command)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Unavailable while the projector refuses the query (ERR3)."""
        return (
            super().available
            and self.entity_description.command.code not in self.coordinator.data.unavailable
        )

    @property
    def native_value(self) -> StateType:
        """Return the decoded value."""
        return self.entity_description.value_fn(self.coordinator.data)


class ValerionSlotSensor(ValerionEntity, SensorEntity):
    """One fan or temperature slot."""

    entity_description: ValerionSlotDescription

    def __init__(
        self,
        coordinator: ValerionCoordinator,
        description: ValerionSlotDescription,
        slot: int,
    ) -> None:
        """Initialize the sensor for ``slot`` (counted from 1)."""
        super().__init__(coordinator, description.command)
        self.entity_description = description
        self._slot = slot
        self._attr_unique_id = f"{self.device_id}_{description.key}_{slot}"
        self._attr_translation_placeholders = {"index": str(slot)}

    @property
    def native_value(self) -> int | None:
        """Return the reading of this slot."""
        raw = self.coordinator.data.value(self.entity_description.command)
        if raw is None:
            return None
        values = parse_number_list(raw)
        return values[self._slot - 1] if self._slot <= len(values) else None
