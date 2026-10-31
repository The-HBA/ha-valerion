"""Media player entity for the Valerion integration.

This is the main entity of the device: power, input source, volume and mute.
Picture settings live on dedicated select / number entities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN, SOURCE_NAMES
from .entity import ValerionEntity
from .lib import VOLUME_MAX, MuteState, PowerState, protocol

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import ValerionConfigEntry, ValerionCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValerionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the media player for a config entry."""
    async_add_entities([ValerionMediaPlayer(entry.runtime_data)])


class ValerionMediaPlayer(ValerionEntity, MediaPlayerEntity):
    """The projector as a media player."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.PROJECTOR
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
    )

    def __init__(self, coordinator: ValerionCoordinator) -> None:
        """Initialize the media player."""
        super().__init__(coordinator, protocol.POWER)
        self._attr_unique_id = f"{self.device_id}_media_player"

    @property
    def available(self) -> bool:
        """Stay available while off so ``turn_on`` can wake the projector."""
        return self._power_control_available

    @property
    def state(self) -> MediaPlayerState | None:
        """Return on, standby or off; the projector has no playback state."""
        power = self.coordinator.data.power
        return _POWER_TO_STATE.get(power) if power is not None else None

    @property
    def assumed_state(self) -> bool:
        """The state is assumed while another controller holds the session."""
        return self.coordinator.data.busy

    @property
    def source_list(self) -> list[str]:
        """Return the input names."""
        inputs = self.coordinator.data.identity.inputs or tuple(SOURCE_NAMES)
        return [SOURCE_NAMES.get(code, f"Input {code}") for code in inputs]

    @property
    def source(self) -> str | None:
        """Return the active input name."""
        code = self.coordinator.data.value(protocol.INPUT) or self.coordinator.data.value(
            protocol.INPUT_CLASS1
        )
        if code is None:
            return None
        return SOURCE_NAMES.get(code, f"Input {code}")

    @property
    def volume_level(self) -> float | None:
        """Return the volume as 0..1."""
        raw = self.coordinator.data.value(protocol.VOLUME)
        try:
            return int(raw) / VOLUME_MAX if raw is not None else None
        except ValueError:
            return None

    @property
    def is_volume_muted(self) -> bool | None:
        """Return the audio mute state."""
        raw = self.coordinator.data.value(protocol.AUDIO_MUTE)
        if raw is None:
            return None
        return raw == MuteState.MUTED

    async def async_turn_on(self) -> None:
        """Wake the projector (Wake-on-LAN) and switch it on."""
        await self.coordinator.async_power_on()

    async def async_turn_off(self) -> None:
        """Put the projector in standby, or fully off if configured so."""
        await self.coordinator.async_power_off()

    async def async_select_source(self, source: str) -> None:
        """Switch to ``source`` by its display name."""
        code = next((c for c, n in SOURCE_NAMES.items() if n == source), None)
        if code is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={"source": source},
            )
        await self.coordinator.async_send(protocol.INPUT, code)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume from 0..1."""
        await self.coordinator.async_send(protocol.VOLUME, round(volume * VOLUME_MAX))

    async def async_volume_up(self) -> None:
        """Step the volume up."""
        await self.coordinator.async_press_key(protocol.VOLUME_STEP, 1)
        await self.coordinator.async_request_refresh()

    async def async_volume_down(self) -> None:
        """Step the volume down."""
        await self.coordinator.async_press_key(protocol.VOLUME_STEP, 0)
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the audio."""
        await self.coordinator.async_send(
            protocol.AUDIO_MUTE, MuteState.MUTED if mute else MuteState.UNMUTED
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose a few raw facts that have no entity of their own yet."""
        data = self.coordinator.data
        return {
            "power_state": data.power.name.lower() if data.power else None,
            "connection": data.connection,
            "busy": data.busy,
        }


_POWER_TO_STATE: dict[PowerState, MediaPlayerState] = {
    PowerState.ON: MediaPlayerState.ON,
    PowerState.STANDBY: MediaPlayerState.STANDBY,
    PowerState.OFF: MediaPlayerState.OFF,
}
