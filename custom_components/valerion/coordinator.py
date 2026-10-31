"""Data update coordinator for the Valerion integration.

One coordinator per projector. It opens a short AWOL Link session on every
poll, asks only for what the enabled entities need, and closes the session
again so the Valerion app and VMote are never locked out.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_POWER_OFF_MODE,
    DEFAULT_POWER_OFF_MODE,
    DOMAIN,
    INTERVAL_IDLE,
    INTERVAL_ON,
    INTERVAL_TRANSITION,
    NAME,
    POWER_OFF_MODE_FULL,
    POWER_ON_RETRY,
    POWER_ON_TIMEOUT,
    SILENT_POLLS_BEFORE_STANDBY,
    SLOW_TIER_EVERY,
    WOL_RESEND,
)
from .lib import (
    DEFAULT_BROADCAST,
    AwolLinkAuthError,
    AwolLinkClient,
    AwolLinkCommandError,
    AwolLinkConnectionError,
    AwolLinkRefusedError,
    AwolLinkUnresponsiveError,
    Command,
    DeviceIdentity,
    KeyPress,
    LockTable,
    PowerState,
    SignalInfo,
    protocol,
    send_magic_packet,
    split_multi_value,
    split_picture_mode_list,
)
from .lib.locks import hdr_key

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

type ValerionConfigEntry = ConfigEntry[ValerionCoordinator]

#: Version of the stored learned locks (``.storage/valerion.<entry id>.locks``).
LOCK_STORE_VERSION: Final = 1


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
#: Settings that can be locked for a signal format and picture mode (ERR3
#: on a set, see ``lib/locks.py``).
_LOCKABLE: Final[tuple[Command, ...]] = (
    protocol.ASPECT_RATIO,
    protocol.GAMMA,
    protocol.DYNAMIC_TONE_MAPPING,
    protocol.COLOR_TEMPERATURE,
    protocol.ENHANCED_BLACK_LEVEL,
    protocol.MOTION_ENHANCEMENT,
    protocol.LASER_LEVEL,
)
#: Commands an entity needs in addition to its own context: the picture mode
#: select needs the list of modes valid for the current signal, and a
#: lockable setting needs the signal format and picture mode its locks
#: depend on (also when the HDR format sensor is disabled).
_EXTRA_CONTEXT: Final[dict[str, tuple[Command, ...]]] = {
    protocol.PICTURE_MODE.code: (protocol.PICTURE_MODE_LIST,),
    **{cmd.code: (protocol.SIGNAL_INFO, protocol.PICTURE_MODE) for cmd in _LOCKABLE},
}
#: Command errors with a clearer explanation than ``setting_locked`` (ERR3) or
#: ``command_rejected``, keyed by (error, command code).
_ERROR_MESSAGES: Final[dict[tuple[str, str], str]] = {
    (protocol.ERR_PARAMETER, protocol.COLOR_TEMPERATURE.code): "color_temperature_rejected",
    (protocol.ERR_PARAMETER, protocol.MOTION_ENHANCEMENT.code): "motion_mode_rejected",
    (protocol.ERR_PARAMETER, protocol.ASPECT_RATIO.code): "aspect_ratio_rejected",
    (protocol.ERR_UNAVAILABLE, protocol.LENS_SHIFT_MENU.code): "lens_menu_unavailable",
    (protocol.ERR_UNAVAILABLE, protocol.ZOOM_MENU.code): "lens_menu_unavailable",
    (protocol.ERR_UNAVAILABLE, protocol.FOCUS_MENU.code): "lens_menu_unavailable",
}
#: Menus a model may lack altogether (no motorised lens shift, zoom or
#: focus); an ERR3 while the projector is on marks them unsupported.
_MENU_CODES: Final = frozenset(
    cmd.code for cmd in (protocol.LENS_SHIFT_MENU, protocol.ZOOM_MENU, protocol.FOCUS_MENU)
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
    #: Settings locked for the current signal format and picture mode, known
    #: in advance or learned from an earlier refused change.
    locked: frozenset[str] = frozenset()
    #: Command codes this projector does not support (learned, see ``_MENU_CODES``).
    unsupported: frozenset[str] = frozenset()
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

    def is_locked(self, command: Command) -> bool:
        """Return True if ``command`` cannot be changed for the current signal."""
        return command.code in self.unavailable or command.code in self.locked


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
        #: Codes answered with ERR3 (locked for the current signal). Kept until
        #: the code is read successfully again, because slow-tier codes are
        #: only queried about once a minute.
        self._unavailable: set[str] = set()
        #: Set after a picture-mode change: every picture setting belongs to
        #: the mode, so the slow tier is read again on the next poll.
        self._settings_stale = False
        #: The picture mode for which a missing list entry was last re-read.
        self._list_checked_for: str | None = None
        self._identity = DeviceIdentity()
        self._identity_loaded = False
        self._silent_polls = 0
        self._poll_counter = 0
        self._transition_until: float | None = None
        self._last_power: PowerState | None = None
        self._locks = LockTable()
        self._lock_store = lock_store(hass, entry.entry_id)
        #: The last Wake-on-LAN attempt, for diagnostics.
        self.last_wake: dict[str, Any] | None = None

    async def async_load_locks(self) -> None:
        """Load the locks learned before the last restart."""
        self._locks = LockTable.from_dict(await self._lock_store.async_load())

    def locks_as_dict(self) -> dict[str, Any]:
        """Return the learned locks for diagnostics."""
        return self._locks.as_dict()

    # ------------------------------------------------------------------ polling
    async def _async_update_data(self) -> ProjectorData:
        wanted = {ctx.code for ctx in self.async_contexts() if isinstance(ctx, Command)}
        wanted |= {extra.code for code in wanted for extra in _EXTRA_CONTEXT.get(code, ())}
        try:
            async with self.client.session() as session:
                power_raw = await session.query(protocol.POWER)
                power = _as_power(power_raw)
                self._values[protocol.POWER.code] = power_raw
                if power == PowerState.ON:
                    if self._last_power != PowerState.ON:
                        self._identity_loaded = False  # re-read after every power-on
                    await self._poll_on(session, wanted)
                else:
                    self._forget_volatile()
                    if not self._identity_loaded:
                        self._store(await session.query_many(list(STATIC_COMMANDS)))
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
        return self._snapshot(Connection.ANSWERING, power)

    async def _poll_on(self, session: Any, wanted: set[str]) -> None:
        self._poll_counter += 1
        commands: list[Command] = [cmd for cmd in CORE_COMMANDS if cmd is not protocol.POWER]
        commands += [cmd for cmd in FAST_COMMANDS if cmd.code in wanted]
        slow_due = (
            self._poll_counter % SLOW_TIER_EVERY == 1
            or not self._identity_loaded
            or self._settings_stale
        )
        slow = [cmd for cmd in SLOW_COMMANDS if cmd.code in wanted]
        if slow_due:
            commands += slow
            self._settings_stale = False
        if not self._identity_loaded:
            commands += list(STATIC_COMMANDS)

        self._store(await session.query_many(commands))
        if not self._identity_loaded:
            self._apply_identity()
        mode = self._values.get(protocol.PICTURE_MODE.code)
        if not slow_due and mode != self._list_checked_for and self._mode_not_listed(wanted):
            # The signal format changed (SDR -> HDR10 ...): the active mode is
            # not in the known list, so read the new list and the settings now.
            # Only once per mode: some lists never contain the active mode.
            self._list_checked_for = mode
            self._store(await session.query_many(slow))

    def _mode_not_listed(self, wanted: set[str]) -> bool:
        if protocol.PICTURE_MODE_LIST.code not in wanted:
            return False
        mode = self._values.get(protocol.PICTURE_MODE.code)
        modes = split_picture_mode_list(self._values.get(protocol.PICTURE_MODE_LIST.code, ""))
        return bool(mode) and mode not in modes

    def _store(self, results: dict[str, str | AwolLinkCommandError]) -> None:
        for code, result in results.items():
            if isinstance(result, AwolLinkCommandError):
                if result.is_unavailable:
                    self._unavailable.add(code)
                    self._values.pop(code, None)
                else:
                    _LOGGER.debug("Query %s failed: %s", code, result)
            else:
                self._values[code] = result
                self._unavailable.discard(code)

    def _apply_identity(self) -> None:
        identity = _identity_from_values(self._values)
        self._identity_loaded = True
        had_locks = bool(self._locks.learned or self._locks.unsupported)
        if self._locks.check_firmware(identity.firmware):
            if had_locks and not (self._locks.learned or self._locks.unsupported):
                _LOGGER.info("Firmware changed to %s; learned locks cleared", identity.firmware)
            self._save_locks()
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
        self._unavailable.clear()

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
        last_error: str | None = None,
    ) -> ProjectorData:
        signal_raw = self._values.get(protocol.SIGNAL_INFO.code)
        picl_raw = self._values.get(protocol.PICTURE_MODE_LIST.code)
        return ProjectorData(
            connection=connection,
            power=power,
            busy=busy,
            values=dict(self._values),
            unavailable=frozenset(self._unavailable),
            locked=self._current_locks(),
            unsupported=self._locks.unsupported,
            identity=self._identity,
            signal=SignalInfo.parse(signal_raw) if signal_raw is not None else None,
            picture_modes=tuple(split_picture_mode_list(picl_raw)) if picl_raw else (),
            last_error=last_error,
        )

    # ----------------------------------------------------------------- commands
    @contextmanager
    def _command_errors(self) -> Iterator[None]:
        """Translate library errors into Home Assistant errors for actions."""
        try:
            yield
        except AwolLinkAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AwolLinkCommandError as err:
            # The failed line starts with its header, for example "%3MOTN 2".
            code = err.command[2:6]
            if err.is_unavailable and code in _MENU_CODES and self._learn_unsupported(code):
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="lens_menu_unsupported",
                    translation_placeholders={"command": err.command},
                ) from err
            key = _ERROR_MESSAGES.get((err.error, code))
            if key is None and err.is_unavailable:
                key = "setting_locked"
            if key is not None:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key=key,
                    translation_placeholders={"command": err.command},
                ) from err
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={"command": err.command, "error": err.error},
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

    async def async_send(self, command: Command, value: str | int) -> None:
        """Send a set command, read the setting back and publish the new state."""
        with self._command_errors():
            async with self.client.session() as session:
                try:
                    await session.send(command, value)
                except AwolLinkCommandError as err:
                    if err.is_unavailable:
                        self._learn_lock(command, value)
                    raise
                try:
                    self._values[command.code] = await session.query(command)
                except AwolLinkCommandError:
                    self._values[command.code] = str(value)
        self._unavailable.discard(command.code)
        self._publish()

    # -------------------------------------------------------------- learned locks
    def _current_locks(self) -> frozenset[str]:
        signal_raw = self._values.get(protocol.SIGNAL_INFO.code)
        if signal_raw is None:
            return frozenset()
        return self._locks.locked(
            SignalInfo.parse(signal_raw).hdr, self._values.get(protocol.PICTURE_MODE.code)
        )

    def _learn_lock(self, command: Command, value: str | int) -> None:
        """Remember that the projector refused ``command`` for this signal and mode.

        Re-sending the current value can also return ERR3 (aspect ratio
        without a signal), which says nothing about the setting, so it is
        not learned. Neither is a refusal before the signal and mode are known.
        """
        signal_raw = self._values.get(protocol.SIGNAL_INFO.code)
        mode = self._values.get(protocol.PICTURE_MODE.code)
        if signal_raw is None or not mode or self._values.get(command.code) == str(value):
            return
        hdr = SignalInfo.parse(signal_raw).hdr
        if self._locks.learn(hdr, mode, command.code):
            _LOGGER.info(
                "Learned that %s is locked with %s in %s", command.code, hdr_key(hdr), mode
            )
            self._save_locks()
            self._publish()

    def _learn_unsupported(self, code: str) -> bool:
        """Remember that this projector lacks a menu; return True if newly learned.

        Only while the projector is on: in standby a refusal says nothing
        about the model.
        """
        if self.data is None or not self.data.is_on or not self._locks.mark_unsupported(code):
            return False
        _LOGGER.info("Learned that this projector does not support %s", code)
        self._save_locks()
        self._publish()
        return True

    async def async_forget_locks(self) -> None:
        """Forget every learned lock and unsupported menu, for example after a mistaken refusal."""
        if self._locks.clear():
            self._save_locks()
            self._publish()

    def _save_locks(self) -> None:
        self._lock_store.async_delay_save(self._locks.as_dict, 1)

    async def async_set_picture_mode(self, mode: str) -> None:
        """Switch the picture mode, then re-read the settings that belong to it.

        Re-sending the active mode returns ERR4 (firmware bug), so it is skipped.
        """
        if self._values.get(protocol.PICTURE_MODE.code) == mode:
            return
        await self.async_send(protocol.PICTURE_MODE, mode)
        self._settings_stale = True
        await self.async_request_refresh()

    async def async_press_key(self, command: Command, value: str | int) -> None:
        """Send a non-idempotent command (remote key) without read-back and never retry."""
        with self._command_errors():
            async with self.client.session() as session:
                await session.send(command, value)

    async def async_press_keys(self, presses: Sequence[KeyPress], *, delay: float) -> None:
        """Send key presses in one short session, ``delay`` seconds apart.

        Keys are never retried: a repeated press could move a menu twice.
        """
        with self._command_errors():
            async with self.client.session() as session:
                for index, press in enumerate(presses):
                    if index and delay > 0:
                        await asyncio.sleep(delay)
                    await session.send(press.command, press.value)

    async def async_send_raw(self, command: Command, value: str) -> str:
        """Send one raw line and return the projector's reply line.

        ERRx replies are returned rather than raised, so the user sees the
        projector's own answer (for example ``%3ASPR=ERR3``).
        """
        with self._command_errors():
            async with self.client.session() as session:
                try:
                    response = await session.raw(command.set(value), expect=command)
                except AwolLinkCommandError as err:
                    return f"{command.header}={err.error}"
        return response.raw

    async def async_power_on(self) -> None:
        """Wake the projector and switch it on.

        With a known MAC address a Wake-on-LAN packet goes out first and again
        every few seconds while ``%1POWR 1`` is retried, until the projector
        greets us or the timeout passes.
        """
        loop = self.hass.loop
        deadline = loop.time() + POWER_ON_TIMEOUT.total_seconds()
        next_wake = loop.time()
        last_error: Exception | None = None
        while True:
            if self.mac and loop.time() >= next_wake:
                await self._async_wake(self.mac)
                next_wake = loop.time() + WOL_RESEND.total_seconds()
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
            if loop.time() >= deadline:
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

    async def _async_wake(self, mac: str) -> None:
        """Send one Wake-on-LAN burst; a failure is logged, not raised.

        The broadcast reaches projectors on Home Assistant's own network; the
        copy sent straight to the projector's address also crosses a router
        to another VLAN.
        """
        targets = (DEFAULT_BROADCAST, self.client.host)
        try:
            sent = await send_magic_packet(mac, targets=targets)
        except OSError as err:
            _LOGGER.warning("Could not send the Wake-on-LAN packet: %s", err)
            self.last_wake = {"time": dt_util.utcnow().isoformat(), "error": str(err)}
            return
        _LOGGER.debug("Wake-on-LAN packet sent to %s", ", ".join(sent))
        self.last_wake = {
            "time": dt_util.utcnow().isoformat(),
            # The projector's address is redacted like the host in diagnostics.
            "sent_to": ["broadcast" if a == DEFAULT_BROADCAST else "projector" for a in sent],
        }

    async def async_power_off(self, *, full: bool | None = None) -> None:
        """Put the projector in standby or switch it fully off.

        Without ``full`` the power-off mode from the integration options applies.
        """
        if full is None:
            mode = self.config_entry.options.get(CONF_POWER_OFF_MODE, DEFAULT_POWER_OFF_MODE)
            full = mode == POWER_OFF_MODE_FULL
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
                unavailable=frozenset(self._unavailable),
                locked=self._current_locks(),
                unsupported=self._locks.unsupported,
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


def configured_mac(entry: ConfigEntry) -> str | None:
    """Return the projector's MAC address for Wake-on-LAN, if one is set.

    The settings (options) win over the first setup, so a MAC can be added,
    changed or removed (empty value) later.
    """
    mac: str | None = (
        entry.options[CONF_MAC] if CONF_MAC in entry.options else entry.data.get(CONF_MAC)
    )
    return mac or None


def lock_store(hass: HomeAssistant, entry_id: str) -> Store[dict[str, Any]]:
    """Return the storage file that keeps the learned locks of one projector."""
    return Store(hass, LOCK_STORE_VERSION, f"{DOMAIN}.{entry_id}.locks")


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
