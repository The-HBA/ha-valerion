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
from .models import HdrFormat

if TYPE_CHECKING:
    from collections.abc import Mapping

#: Locks that hold on every model: measured on the VisionMaster Pro2
#: (firmware V02.01.00E.Q0718, 2026-10-30) and matching AWOL's rule that
#: dynamic tone mapping works in HDR10 only and gamma presets in SDR only.
#: Gamma in HDR10 was refused in every HDR10 picture mode (2026-10-31).
#: HLG and HDR10+ are not measured yet, so their locks are learned.
KNOWN_LOCKS: Final[Mapping[HdrFormat, frozenset[str]]] = {
    HdrFormat.SDR: frozenset({protocol.DYNAMIC_TONE_MAPPING.code}),
    HdrFormat.HDR10: frozenset({protocol.GAMMA.code}),
    HdrFormat.DOLBY_VISION: frozenset({protocol.GAMMA.code, protocol.DYNAMIC_TONE_MAPPING.code}),
}

#: Stored instead of an HDR format while no signal is playing.
NO_SIGNAL: Final = "no_signal"


@dataclass(frozen=True, order=True)
class LearnedLock:
    """One setting the projector refused for a signal format and picture mode."""

    hdr: str  # lower-case ``HdrFormat`` member name or ``NO_SIGNAL``
    picture_mode: str
    code: str


def hdr_key(hdr: HdrFormat | None) -> str:
    """Return the stored name of a signal format, for example ``dolby_vision``."""
    return hdr.name.lower() if hdr is not None else NO_SIGNAL


class LockTable:
    """Known locks plus the locks learned on one projector.

    Learned locks belong to the firmware they were learned on: a firmware
    update may unlock settings, so they are dropped when it changes.
    """

    def __init__(self, firmware: str | None = None, learned: tuple[LearnedLock, ...] = ()) -> None:
        """Initialize the table."""
        self.firmware = firmware
        self._learned: set[LearnedLock] = set(learned)

    @property
    def learned(self) -> tuple[LearnedLock, ...]:
        """Return the learned locks in a stable order."""
        return tuple(sorted(self._learned))

    def locked(self, hdr: HdrFormat | None, picture_mode: str | None) -> frozenset[str]:
        """Return the command codes locked for this signal format and picture mode."""
        known = KNOWN_LOCKS.get(hdr, frozenset()) if hdr is not None else frozenset()
        key = hdr_key(hdr)
        learned = {
            lock.code
            for lock in self._learned
            if lock.hdr == key and lock.picture_mode == picture_mode
        }
        return known | learned

    def learn(self, hdr: HdrFormat | None, picture_mode: str, code: str) -> bool:
        """Remember a refused setting; return True if it was not known yet."""
        if code in self.locked(hdr, picture_mode):
            return False
        self._learned.add(LearnedLock(hdr_key(hdr), picture_mode, code))
        return True

    def clear(self) -> bool:
        """Forget every learned lock; return True if there were any."""
        had_locks = bool(self._learned)
        self._learned.clear()
        return had_locks

    def check_firmware(self, firmware: str | None) -> bool:
        """Note the running firmware; return True if the table changed.

        Learned locks are dropped when the firmware differs from the one
        they were learned on.
        """
        if not firmware or firmware == self.firmware:
            return False
        if self.firmware is not None:
            self._learned.clear()
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
        return cls(firmware if isinstance(firmware, str) else None, tuple(learned))
