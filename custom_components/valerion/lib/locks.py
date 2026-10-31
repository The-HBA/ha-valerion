"""Picture settings that are locked for a signal format and picture mode.

The projector answers a query for a locked setting normally (gamma reads
2.2 while Dolby Vision plays), so only a set command reveals the lock: it
is refused with ``ERR3``. This module combines locks known in advance with
locks learned from such refusals, so a controller can show a locked setting
as unavailable before anyone tries to change it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from . import protocol
from .models import HdrFormat, SignalInfo

if TYPE_CHECKING:
    from collections.abc import Mapping

#: Locks that hold on every model: measured on the VisionMaster Pro2
#: (firmware V02.01.00E.Q0718, 2026-10-30) and matching AWOL's rule that
#: dynamic tone mapping works in HDR10 only and gamma presets in SDR only.
#: Gamma in HDR10 was refused in every HDR10 picture mode (2026-10-31).
#: Gamma and dynamic tone mapping in HDR10+ were refused in HDR10+ Theater
#: and HDR10+ Game (2026-10-31), and in HLG in every HLG picture mode
#: (2026-10-31).
KNOWN_LOCKS: Final[Mapping[HdrFormat, frozenset[str]]] = {
    HdrFormat.SDR: frozenset({protocol.DYNAMIC_TONE_MAPPING.code}),
    HdrFormat.HDR10: frozenset({protocol.GAMMA.code}),
    HdrFormat.HLG: frozenset({protocol.GAMMA.code, protocol.DYNAMIC_TONE_MAPPING.code}),
    HdrFormat.HDR10_PLUS: frozenset({protocol.GAMMA.code, protocol.DYNAMIC_TONE_MAPPING.code}),
    HdrFormat.DOLBY_VISION: frozenset({protocol.GAMMA.code, protocol.DYNAMIC_TONE_MAPPING.code}),
}

#: Locks during 3D (frame packing), whatever the HDR format reads: aspect
#: ratio, motion enhancement and dynamic tone mapping were refused with an
#: MVC film on the Pro2 (firmware V02.01.00E.Q0718, 2026-10-31).
KNOWN_3D_LOCKS: Final = frozenset(
    {
        protocol.ASPECT_RATIO.code,
        protocol.MOTION_ENHANCEMENT.code,
        protocol.DYNAMIC_TONE_MAPPING.code,
    }
)

#: Stored instead of an HDR format while no signal is playing.
NO_SIGNAL: Final = "no_signal"

#: Stored instead of an HDR format while a 3D signal plays. 3D reads as SDR,
#: so without its own name a lock learned in 3D would also hold for 2D films.
THREE_D: Final = "3d"


@dataclass(frozen=True, order=True)
class LearnedLock:
    """One setting the projector refused for a signal format and picture mode."""

    hdr: str  # lower-case ``HdrFormat`` member name, ``THREE_D`` or ``NO_SIGNAL``
    picture_mode: str
    code: str


def signal_key(signal: SignalInfo | None) -> str:
    """Return the stored name of a signal format, for example ``dolby_vision`` or ``3d``."""
    if signal is None:
        return NO_SIGNAL
    if signal.is_3d:
        return THREE_D
    hdr = signal.hdr
    return hdr.name.lower() if hdr is not None else NO_SIGNAL


def _known_locks(signal: SignalInfo | None) -> frozenset[str]:
    if signal is None:
        return frozenset()
    if signal.is_3d:
        return KNOWN_3D_LOCKS
    hdr = signal.hdr
    return KNOWN_LOCKS.get(hdr, frozenset()) if hdr is not None else frozenset()


class LockTable:
    """Known locks plus the locks learned on one projector.

    Learned locks belong to the firmware they were learned on: a firmware
    update may unlock settings, so they are dropped when it changes. The
    table also remembers commands the projector does not support at all,
    whatever the signal (a lens-shift menu on a model without a motorised
    lens), which are dropped the same way.
    """

    def __init__(
        self,
        firmware: str | None = None,
        learned: tuple[LearnedLock, ...] = (),
        unsupported: tuple[str, ...] = (),
    ) -> None:
        """Initialize the table."""
        self.firmware = firmware
        self._learned: set[LearnedLock] = set(learned)
        self._unsupported: set[str] = set(unsupported)

    @property
    def learned(self) -> tuple[LearnedLock, ...]:
        """Return the learned locks in a stable order."""
        return tuple(sorted(self._learned))

    @property
    def unsupported(self) -> frozenset[str]:
        """Return the command codes this projector does not support."""
        return frozenset(self._unsupported)

    def mark_unsupported(self, code: str) -> bool:
        """Remember an unsupported command; return True if it was not known yet."""
        if code in self._unsupported:
            return False
        self._unsupported.add(code)
        return True

    def locked(self, signal: SignalInfo | None, picture_mode: str | None) -> frozenset[str]:
        """Return the command codes locked for this signal and picture mode."""
        key = signal_key(signal)
        learned = {
            lock.code
            for lock in self._learned
            if lock.hdr == key and lock.picture_mode == picture_mode
        }
        return _known_locks(signal) | learned

    def learn(self, signal: SignalInfo | None, picture_mode: str, code: str) -> bool:
        """Remember a refused setting; return True if it was not known yet."""
        if code in self.locked(signal, picture_mode):
            return False
        self._learned.add(LearnedLock(signal_key(signal), picture_mode, code))
        return True

    def clear(self) -> bool:
        """Forget every learned lock and unsupported command; return True if there were any."""
        had_locks = bool(self._learned or self._unsupported)
        self._learned.clear()
        self._unsupported.clear()
        return had_locks

    def check_firmware(self, firmware: str | None) -> bool:
        """Note the running firmware; return True if the table changed.

        Learned locks are dropped when the firmware differs from the one
        they were learned on.
        """
        if not firmware or firmware == self.firmware:
            return False
        if self.firmware is not None:
            self.clear()
        self.firmware = firmware
        return True

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly copy for storage and diagnostics."""
        return {
            "firmware": self.firmware,
            "learned": [
                {"hdr": lock.hdr, "picture_mode": lock.picture_mode, "code": lock.code}
                for lock in self.learned
            ],
            "unsupported": sorted(self._unsupported),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> LockTable:
        """Rebuild a table from :meth:`as_dict`, skipping malformed entries."""
        if not data:
            return cls()
        firmware = data.get("firmware")
        learned: list[LearnedLock] = []
        for item in data.get("learned") or ():
            try:
                learned.append(
                    LearnedLock(str(item["hdr"]), str(item["picture_mode"]), str(item["code"]))
                )
            except KeyError, TypeError:
                continue
        unsupported = data.get("unsupported")
        return cls(
            firmware if isinstance(firmware, str) else None,
            tuple(learned),
            tuple(str(code) for code in unsupported) if isinstance(unsupported, list) else (),
        )
