"""Named key presses: remote keys, volume steps and the lens menus.

Every entry is a documented AWOL Link command. The lens menus are actions
written as queries (``%3LSMN ?`` opens the lens-shift menu and replies
``OK``), so their value is ``?``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from . import protocol
from .models import RemoteKey

if TYPE_CHECKING:
    from .protocol import Command


@dataclass(frozen=True, slots=True)
class KeyPress:
    """One key press: the command and the value that triggers it."""

    command: Command
    value: str

    @property
    def line(self) -> str:
        """Return the wire line, for example ``%3RCNC 4``."""
        return self.command.set(self.value)


KEYS: Final[dict[str, KeyPress]] = {
    "up": KeyPress(protocol.REMOTE_KEY, RemoteKey.UP),
    "down": KeyPress(protocol.REMOTE_KEY, RemoteKey.DOWN),
    "left": KeyPress(protocol.REMOTE_KEY, RemoteKey.LEFT),
    "right": KeyPress(protocol.REMOTE_KEY, RemoteKey.RIGHT),
    "ok": KeyPress(protocol.REMOTE_KEY, RemoteKey.OK),
    "return": KeyPress(protocol.REMOTE_KEY, RemoteKey.RETURN),
    "menu": KeyPress(protocol.REMOTE_KEY, RemoteKey.MENU),
    "settings": KeyPress(protocol.REMOTE_KEY, RemoteKey.SETTINGS),
    "home": KeyPress(protocol.REMOTE_KEY, RemoteKey.HOME),
    "volume_up": KeyPress(protocol.VOLUME_STEP, "1"),
    "volume_down": KeyPress(protocol.VOLUME_STEP, "0"),
    "lens_shift": KeyPress(protocol.LENS_SHIFT_MENU, "?"),
    "zoom": KeyPress(protocol.ZOOM_MENU, "?"),
    "focus": KeyPress(protocol.FOCUS_MENU, "?"),
}


def key_press(name: str) -> KeyPress:
    """Return the key press for ``name`` (case and surrounding spaces ignored).

    Raises :class:`KeyError` for an unknown name.
    """
    return KEYS[name.strip().lower()]
