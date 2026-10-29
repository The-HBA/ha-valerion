"""AWOL Link wire protocol: framing, commands, responses and authentication.

AWOL Link is the PJLink-style control protocol used by Valerion (AWOL Vision)
projectors. Every message is a single text line terminated by a carriage
return. A command looks like ``%1POWR 1``, a query like ``%1POWR ?`` and the
projector answers with ``%1POWR=OK`` or ``%1POWR=<value>``.

This module has no network code and no Home Assistant imports; it only knows
how to build and parse lines.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Final

TERMINATOR: Final = "\r"
ENCODING: Final = "utf-8"

GREETING_PREFIX: Final = "PJLINK"
GREETING_NO_AUTH: Final = "PJLINK 0"
GREETING_AUTH: Final = "PJLINK 1"
GREETING_AUTH_OK: Final = "PJLINK 1 OK"
GREETING_AUTH_FAILED: Final = "PJLINK ERRA"

ERR_UNDEFINED: Final = "ERR1"
ERR_PARAMETER: Final = "ERR2"
ERR_UNAVAILABLE: Final = "ERR3"
ERR_DEVICE: Final = "ERR4"
ERR_AUTH: Final = "ERRA"

ERROR_CODES: Final[dict[str, str]] = {
    ERR_UNDEFINED: "undefined command or feature not installed",
    ERR_PARAMETER: "invalid parameter",
    ERR_UNAVAILABLE: "command not available in the current state",
    ERR_DEVICE: "projector malfunction",
    ERR_AUTH: "authentication failed",
}

_RESPONSE_RE: Final = re.compile(r"^%(?P<cls>[0-9])(?P<code>[A-Z0-9]{4})=(?P<value>.*)$", re.DOTALL)


class AwolLinkProtocolError(ValueError):
    """Raised when a line from the projector cannot be understood."""


@dataclass(frozen=True, slots=True)
class Command:
    """A command code together with its PJLink class.

    ``Command(1, "POWR")`` renders as ``%1POWR`` on the wire.
    """

    pjlink_class: int
    code: str

    @property
    def header(self) -> str:
        """Return the wire header, for example ``%1POWR``."""
        return f"%{self.pjlink_class}{self.code}"

    def query(self) -> str:
        """Return the query line (without terminator)."""
        return f"{self.header} ?"

    def set(self, value: str | int) -> str:
        """Return the set line for ``value`` (without terminator)."""
        return f"{self.header} {value}"

    def __str__(self) -> str:
        """Return the header."""
        return self.header


# --- Class 1: standard PJLink -------------------------------------------------
POWER: Final = Command(1, "POWR")
INPUT_CLASS1: Final = Command(1, "INPT")
AUDIO_MUTE: Final = Command(1, "AVMT")
INPUT_LIST_CLASS1: Final = Command(1, "INST")
NAME: Final = Command(1, "NAME")
MANUFACTURER: Final = Command(1, "INF1")
MODEL: Final = Command(1, "INF2")
OTHER_INFO: Final = Command(1, "INFO")
PJLINK_CLASS: Final = Command(1, "CLSS")

# --- Class 2 ------------------------------------------------------------------
SEARCH: Final = Command(2, "SRCH")  # UDP discovery only
INPUT: Final = Command(2, "INPT")
INPUT_LIST: Final = Command(2, "INST")
SOFTWARE_VERSION: Final = Command(2, "SVER")
INPUT_NAME: Final = Command(2, "INNM")
INPUT_RESOLUTION: Final = Command(2, "IRES")
RECOMMENDED_RESOLUTION: Final = Command(2, "RRES")
VOLUME_STEP: Final = Command(2, "SVOL")  # 0 = down, 1 = up
ERROR_STATUS: Final = Command(2, "ERST")

# --- Class 3: AWOL specific ---------------------------------------------------
REMOTE_KEY: Final = Command(3, "RCNC")
VOLUME: Final = Command(3, "VOLM")
PICTURE_MODE_LIST: Final = Command(3, "PICL")
PICTURE_MODE: Final = Command(3, "PICT")
LASER_LEVEL: Final = Command(3, "LASL")
ENHANCED_BLACK_LEVEL: Final = Command(3, "ENBL")
MOTION_ENHANCEMENT: Final = Command(3, "MOTN")
GAMMA: Final = Command(3, "GAMA")
DYNAMIC_TONE_MAPPING: Final = Command(3, "DYTM")
COLOR_TEMPERATURE: Final = Command(3, "CLTP")
LENS_SHIFT_MENU: Final = Command(3, "LSMN")
ZOOM_MENU: Final = Command(3, "ZMMN")
FOCUS_MENU: Final = Command(3, "FCMN")
ASPECT_RATIO: Final = Command(3, "ASPR")
SIGNAL_INFO: Final = Command(3, "SINF")
FAN_SPEED: Final = Command(3, "FANS")
TEMPERATURE: Final = Command(3, "TEMP")
LED_STATUS: Final = Command(3, "LEDS")

ALL_QUERYABLE: Final[tuple[Command, ...]] = (
    POWER,
    INPUT_CLASS1,
    AUDIO_MUTE,
    INPUT_LIST_CLASS1,
    NAME,
    MANUFACTURER,
    MODEL,
    OTHER_INFO,
    PJLINK_CLASS,
    INPUT,
    INPUT_LIST,
    SOFTWARE_VERSION,
    INPUT_NAME,
    INPUT_RESOLUTION,
    RECOMMENDED_RESOLUTION,
    ERROR_STATUS,
    VOLUME,
    PICTURE_MODE_LIST,
    PICTURE_MODE,
    LASER_LEVEL,
    ENHANCED_BLACK_LEVEL,
    MOTION_ENHANCEMENT,
    GAMMA,
    DYNAMIC_TONE_MAPPING,
    COLOR_TEMPERATURE,
    ASPECT_RATIO,
    SIGNAL_INFO,
    FAN_SPEED,
    TEMPERATURE,
    LED_STATUS,
)


@dataclass(frozen=True, slots=True)
class Response:
    """A parsed response line such as ``%1POWR=1``."""

    pjlink_class: int
    code: str
    value: str
    raw: str

    @property
    def header(self) -> str:
        """Return the wire header, for example ``%1POWR``."""
        return f"%{self.pjlink_class}{self.code}"

    @property
    def is_error(self) -> bool:
        """Return True if the value is one of the ERRx codes."""
        return self.value in ERROR_CODES

    @property
    def is_ok(self) -> bool:
        """Return True if the projector acknowledged a set command."""
        return self.value == "OK"

    def matches(self, command: Command) -> bool:
        """Return True if this response answers ``command``.

        The class digit is compared loosely because some firmware answers a
        class 2 query with a class 1 header.
        """
        return self.code == command.code


def encode_line(line: str) -> bytes:
    """Encode a command line for the wire (adds the terminator)."""
    if TERMINATOR in line or "\n" in line:
        msg = f"command must not contain line terminators: {line!r}"
        raise AwolLinkProtocolError(msg)
    return f"{line}{TERMINATOR}".encode(ENCODING)


def decode_line(data: bytes) -> str:
    """Decode a raw line from the wire and strip terminators and padding."""
    try:
        text = data.decode(ENCODING)
    except UnicodeDecodeError as err:
        msg = f"line is not valid UTF-8: {data!r}"
        raise AwolLinkProtocolError(msg) from err
    return text.strip("\x00\r\n")


def parse_response(line: str) -> Response:
    """Parse a response line into a :class:`Response`."""
    match = _RESPONSE_RE.match(line)
    if match is None:
        msg = f"malformed response: {line!r}"
        raise AwolLinkProtocolError(msg)
    return Response(
        pjlink_class=int(match["cls"]),
        code=match["code"],
        value=match["value"].strip(),
        raw=line,
    )


@dataclass(frozen=True, slots=True)
class Greeting:
    """The first line the projector sends after a TCP connection is opened."""

    auth_required: bool
    random_token: str | None
    raw: str


def parse_greeting(line: str) -> Greeting:
    """Parse the ``PJLINK 0`` / ``PJLINK 1 <random>`` greeting."""
    text = line.strip()
    if text.startswith(GREETING_AUTH_FAILED):
        return Greeting(auth_required=True, random_token=None, raw=text)
    if text.startswith(GREETING_AUTH):
        parts = text.split()
        token = parts[2] if len(parts) >= 3 else None  # noqa: PLR2004
        return Greeting(auth_required=True, random_token=token, raw=text)
    if text.startswith(GREETING_NO_AUTH):
        return Greeting(auth_required=False, random_token=None, raw=text)
    msg = f"unexpected greeting: {text!r}"
    raise AwolLinkProtocolError(msg)


def auth_digest(security_code: str, random_token: str) -> str:
    """Return the authentication digest expected by AWOL Link.

    Standard PJLink hashes ``random + password``. AWOL Link hashes
    ``code + random`` and expects the digest on its own line, followed by the
    ``PJLINK 1 OK`` acknowledgement. The digest is lowercase hexadecimal.
    """
    return hashlib.md5(  # noqa: S324 - mandated by the protocol
        f"{security_code}{random_token}".encode(ENCODING)
    ).hexdigest()
