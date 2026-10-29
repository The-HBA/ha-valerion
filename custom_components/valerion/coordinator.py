"""Data update coordinator for the Valerion integration.

One coordinator per projector. It opens a short AWOL Link session on every
poll, asks only for what the enabled entities need, and closes the session
again so the Valerion app and VMote are never locked out.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    INTERVAL_IDLE,
    INTERVAL_ON,
    INTERVAL_TRANSITION,
    NAME,
    POWER_ON_RETRY,
    POWER_ON_TIMEOUT,
    SILENT_POLLS_BEFORE_STANDBY,
    SLOW_TIER_EVERY,
)
from .lib import (
    AwolLinkAuthError,
    AwolLinkClient,
    AwolLinkCommandError,
    AwolLinkConnectionError,
    AwolLinkRefusedError,
    AwolLinkUnresponsiveError,
    Command,
    DeviceIdentity,
    PowerState,
    SignalInfo,
    protocol,
    send_magic_packet,
    split_multi_value,
    split_picture_mode_list,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

type ValerionConfigEntry = ConfigEntry[ValerionCoordinator]


class Connection(StrEnum):
    """How the last poll went (also the states of the AWOL Link status sensor)."""

    ANSWERING = "answering"  # greeted us and answered
    SILENT = "silent"  # TCP accepted, no greeting: standby or busy
    REFUSED = "refused"  # TCP refused: AWOL Link switched off on the projector
    UNREACHABLE = "unreachable"  # no route, or the connection timed out


#: Queried on every poll while the projector is on.
CORE_COMMANDS: Final[tuple[Command, ...]] = (
    protocol.POWER,
    protocol.INPUT,
    protocol.AUDIO_MUTE,
    protocol.VOLUME,
)
#: Queried on every poll, but only if an enabled entity asked for them.
FAST_COMMANDS: Final[tuple[Command, ...]] = (
    protocol.PICTURE_MODE,
    protocol.INPUT_RESOLUTION,
    protocol.SIGNAL_INFO,
)
#: Queried about once a minute, only if an enabled entity asked for them.
SLOW_COMMANDS: Final[tuple[Command, ...]] = (
    protocol.PICTURE_MODE_LIST,
    protocol.LASER_LEVEL,
    protocol.ENHANCED_BLACK_LEVEL,
    protocol.MOTION_ENHANCEMENT,
    protocol.GAMMA,
    protocol.DYNAMIC_TONE_MAPPING,
    protocol.COLOR_TEMPERATURE,
    protocol.ASPECT_RATIO,
    protocol.FAN_SPEED,
    protocol.TEMPERATURE,
    protocol.LED_STATUS,
)
#: Queried when the projector starts answering (light standby answers them
#: too, observed on the Pro2) and again after every power-on.
STATIC_COMMANDS: Final[tuple[Command, ...]] = (
    protocol.MANUFACTURER,
    protocol.MODEL,
    protocol.NAME,
    protocol.SOFTWARE_VERSION,
    protocol.PJLINK_CLASS,
    protocol.OTHER_INFO,
    protocol.INPUT_LIST,
    protocol.RECOMMENDED_RESOLUTION,
)
#: Values that only make sense while the projector is on.
_VOLATILE_CODES: Final = frozenset(
    cmd.code for cmd in (*CORE_COMMANDS, *FAST_COMMANDS, *SLOW_COMMANDS)
) - {protocol.POWER.code}


@dataclass(frozen=True)
class ProjectorData:
    """Snapshot shared with the entities."""

    connection: Connection = Connection.UNREACHABLE
    power: PowerState | None = None
    #: True while an "on" projector is silent, probably because another
    #: controller (Valerion app, VMote) holds the single control session.
    busy: bool = False
    #: Raw reply values keyed by command code, for example ``{"POWR": "1"}``.
    values: dict[str, str] = field(default_factory=dict)
    #: Command codes the projector answered with ERR3 (locked for this signal).
    unavailable: frozenset[str] = frozenset()
    identity: DeviceIdentity = field(default_factory=DeviceIdentity)
    signal: SignalInfo | None = None
    picture_modes: tuple[str, ...] = ()
    last_error: str | None = None

    @property
    def is_on(self) -> bool:
        """Return True if the projector reports itself on (or is busy but was on)."""
        return self.power == PowerState.ON

    def value(self, command: Command) -> str | None:
        """Return the raw value for ``command`` if known."""
        return self.values.get(command.code)


class ValerionCoordinator(DataUpdateCoordinator[ProjectorData]):
    """Polls one projector and executes commands against it."""

    config_entry: ValerionConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ValerionConfigEntry,
        client: AwolLinkClient,
        *,
        mac: str | None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=INTERVAL_IDLE,
            always_update=False,
        )
        self.client = client
        self.mac = mac
        #: Device registry identifier, shared by all entities of this projector.
        self.device_id: str = entry.unique_id or entry.entry_id
        self._values: dict[str, str] = {}
        self._identity = DeviceIdentity()
        self._identity_loaded = False
        self._silent_polls = 0
        self._poll_counter = 0
        self._transition_until: float | None = None
        self._last_power: PowerState | None = None

    # ------------------------------------------------------------------ polling
    async def _async_update_data(self) -> ProjectorData:
        wanted = {ctx.code for ctx in self.async_contexts() if isinstance(ctx, Command)}
        try:
            async with self.client.session() as session:
                power_raw = await session.query(protocol.POWER)
                power = _as_power(power_raw)
                self._values[protocol.POWER.code] = power_raw
                unavailable: set[str] = set()
                if power == PowerState.ON:
                    if self._last_power != PowerState.ON:
                        self._identity_loaded = False  # re-read after every power-on
                    await self._poll_on(session, wanted, unavailable)
                else:
                    self._forget_volatile()
                    if not self._identity_loaded:
                        results = await session.query_many(list(STATIC_COMMANDS))
                        self._store(results, unavailable)
                        self._apply_identity()
        except AwolLinkAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AwolLinkUnresponsiveError as err:
            return self._handle_silent(str(err))
        except AwolLinkRefusedError as err:
            return self._handle_refused(str(err))
        except AwolLinkConnectionError as err:
            return self._handle_unreachable(str(err))

        self._silent_polls = 0
        self._last_power = power
        self._set_interval(power)
        return self._snapshot(Connection.ANSWERING, power, unavailable=frozenset(unavailable))

    async def _poll_on(self, session: Any, wanted: set[str], unavailable: set[str]) -> None:
        self._poll_counter += 1
        commands: list[Command] = [cmd for cmd in CORE_COMMANDS if cmd is not protocol.POWER]
        commands += [cmd for cmd in FAST_COMMANDS if cmd.code in wanted]
        slow_due = self._poll_counter % SLOW_TIER_EVERY == 1 or not self._identity_loaded
        if slow_due:
            commands += [cmd for cmd in SLOW_COMMANDS if cmd.code in wanted]
        if not self._identity_loaded:
            commands += list(STATIC_COMMANDS)

        results = await session.query_many(commands)
        self._store(results, unavailable)
        if not self._identity_loaded:
            self._apply_identity()

    def _store(self, results: dict[str, str | AwolLinkCommandError], unavailable: set[str]) -> None:
        for code, result in results.items():
            if isinstance(result, AwolLinkCommandError):
                if result.is_unavailable:
                    unavailable.add(code)
                    self._values.pop(code, None)
                else:
                    _LOGGER.debug("Query %s failed: %s", code, result)
            else:
                self._values[code] = result

    def _apply_identity(self) -> None:
        identity = _identity_from_values(self._values)
        self._identity_loaded = True
        if identity != self._identity:
            self._identity = identity
            self._update_device_registry()

    def device_details(self) -> DeviceInfo:
        """Return the model, name and firmware shown on the device page."""
        return DeviceInfo(
            model=self._identity.model or NAME,
            name=self._identity.name or self.config_entry.title,
            sw_version=self._identity.firmware,
        )

    def _update_device_registry(self) -> None:
        # Entities write the device info only when they are created. If the
        # identity arrives later (or changes after a firmware update), correct
        # the existing device entry. Before the first setup there is none yet.
        registry = dr.async_get(self.hass)
        device = registry.async_get_device(identifiers={(DOMAIN, self.device_id)})
        if device is None:
            return
        details = self.device_details()
        registry.async_update_device(
            device.id,
            model=details.get("model"),
            name=details.get("name"),
            sw_version=details.get("sw_version"),
        )

    def _handle_silent(self, error: str) -> ProjectorData:
        self._silent_polls += 1
        was_on = self._last_power == PowerState.ON
        if was_on and self._silent_polls <= SILENT_POLLS_BEFORE_STANDBY:
            _LOGGER.debug(
                "%s silent while on (%s/%s); assuming another controller is connected",
                self.client.host,
                self._silent_polls,
                SILENT_POLLS_BEFORE_STANDBY,
            )
            return self._snapshot(Connection.SILENT, PowerState.ON, busy=True, last_error=error)
        self._forget_volatile()
        self._identity_loaded = False
        self._last_power = PowerState.STANDBY
        self._set_interval(PowerState.STANDBY)
        return self._snapshot(Connection.SILENT, PowerState.STANDBY, last_error=error)

    def _handle_refused(self, error: str) -> ProjectorData:
        # On the network but AWOL Link is off, so the power state is unknown.
        self._forget_volatile()
        self._identity_loaded = False
        self._last_power = None
        self._set_interval(None)
        return self._snapshot(Connection.REFUSED, None, last_error=error)

    def _handle_unreachable(self, error: str) -> ProjectorData:
        self._forget_volatile()
        self._identity_loaded = False
        self._last_power = PowerState.OFF
        self._set_interval(PowerState.OFF)
        return self._snapshot(Connection.UNREACHABLE, PowerState.OFF, last_error=error)

    def _forget_volatile(self) -> None:
        for code in _VOLATILE_CODES:
            self._values.pop(code, None)

    def _set_interval(self, power: PowerState | None) -> None:
        loop_time = self.hass.loop.time()
        if self._transition_until is not None and loop_time < self._transition_until:
            self.update_interval = INTERVAL_TRANSITION
            return
        self._transition_until = None
        self.update_interval = INTERVAL_ON if power == PowerState.ON else INTERVAL_IDLE

    def _snapshot(
        self,
        connection: Connection,
        power: PowerState | None,
        *,
        busy: bool = False,
        unavailable: frozenset[str] = frozenset(),
        last_error: str | None = None,
    ) -> ProjectorData:
        signal_raw = self._values.get(protocol.SIGNAL_INFO.code)
        picl_raw = self._values.get(protocol.PICTURE_MODE_LIST.code)
        return ProjectorData(
            connection=connection,
            power=power,
            busy=busy,
            values=dict(self._values),
            unavailable=unavailable,
            identity=self._identity,
            signal=SignalInfo.parse(signal_raw) if signal_raw is not None else None,
            picture_modes=tuple(split_picture_mode_list(picl_raw)) if picl_raw else (),
            last_error=last_error,
        )

    # ----------------------------------------------------------------- commands
    async def async_send(self, command: Command, value: str | int) -> None:
        """Send a set command, read the setting back and publish the new state."""
        try:
            async with self.client.session() as session:
                await session.send(command, value)
                try:
                    self._values[command.code] = await session.query(command)
                except AwolLinkCommandError:
                    self._values[command.code] = str(value)
        except AwolLinkAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AwolLinkCommandError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={"command": command.header, "error": err.error},
            ) from err
        except AwolLinkUnresponsiveError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="projector_asleep",
            ) from err
        except AwolLinkConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err
        self._publish()

    async def async_press_key(self, command: Command, value: str | int) -> None:
        """Send a non-idempotent command (remote key) without read-back and never retry."""
        try:
            async with self.client.session() as session:
                await session.send(command, value)
        except AwolLinkAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AwolLinkCommandError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={"command": command.header, "error": err.error},
            ) from err
        except AwolLinkUnresponsiveError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="projector_asleep"
            ) from err
        except AwolLinkConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err

    async def async_power_on(self) -> None:
        """Wake the projector and switch it on.

        Sends a Wake-on-LAN packet when a MAC address is known, then retries
        ``%1POWR 1`` until the projector greets us or the timeout passes.
        """
        if self.mac:
            await send_magic_packet(self.mac)
        deadline = self.hass.loop.time() + POWER_ON_TIMEOUT.total_seconds()
        last_error: Exception | None = None
        while True:
            try:
                async with self.client.session() as session:
                    await session.send(protocol.POWER, PowerState.ON)
                break
            except AwolLinkAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except AwolLinkCommandError as err:
                if err.is_unavailable:
                    break  # already on or warming up
                last_error = err
            except AwolLinkConnectionError as err:
                last_error = err
            if self.hass.loop.time() >= deadline:
                if self.mac:
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="power_on_timeout",
                        translation_placeholders={"error": str(last_error)},
                    ) from last_error
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="power_on_needs_mac",
                ) from last_error
            await asyncio.sleep(POWER_ON_RETRY.total_seconds())
        self._begin_transition()

    async def async_power_off(self, *, full: bool) -> None:
        """Put the projector in standby (default) or switch it fully off."""
        target = PowerState.OFF if full else PowerState.STANDBY
        await self.async_press_key(protocol.POWER, target)
        self._values[protocol.POWER.code] = target
        self._forget_volatile()
        self._last_power = target
        self._begin_transition()

    def _begin_transition(self) -> None:
        self._transition_until = self.hass.loop.time() + 60
        self.update_interval = INTERVAL_TRANSITION
        self._publish()
        self.config_entry.async_create_background_task(
            self.hass, self.async_request_refresh(), f"{DOMAIN}_refresh_after_power"
        )

    def _publish(self) -> None:
        current = self.data or ProjectorData()
        power = _as_power(self._values.get(protocol.POWER.code))
        self.async_set_updated_data(
            replace(
                current,
                power=power,
                values=dict(self._values),
                signal=(
                    SignalInfo.parse(self._values[protocol.SIGNAL_INFO.code])
                    if protocol.SIGNAL_INFO.code in self._values
                    else None
                ),
                picture_modes=tuple(
                    split_picture_mode_list(self._values.get(protocol.PICTURE_MODE_LIST.code, ""))
                ),
            )
        )


def _as_power(raw: str | None) -> PowerState | None:
    try:
        return PowerState(raw) if raw is not None else None
    except ValueError:
        _LOGGER.debug("Unknown power value %r", raw)
        return None


def _identity_from_values(values: dict[str, str]) -> DeviceIdentity:
    inputs_raw = values.get(protocol.INPUT_LIST.code, "")
    return DeviceIdentity(
        manufacturer=values.get(protocol.MANUFACTURER.code),
        model=values.get(protocol.MODEL.code),
        name=values.get(protocol.NAME.code),
        software_version=values.get(protocol.SOFTWARE_VERSION.code) or None,
        pjlink_class=values.get(protocol.PJLINK_CLASS.code),
        color=values.get(protocol.OTHER_INFO.code),
        inputs=tuple(split_multi_value(inputs_raw)) if inputs_raw else (),
        recommended_resolution=values.get(protocol.RECOMMENDED_RESOLUTION.code),
    )
