"""Value enumerations and data models for AWOL Link.

The numeric codes come from the "Response Data" sheet of the official AWOL
Link command list, which is the authoritative source where the two sheets
disagree (motion enhancement).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final


class PowerState(StrEnum):
    """Power states reported by ``%1POWR ?``."""

    STANDBY = "0"
    ON = "1"
    OFF = "2"


class Input(StrEnum):
    """Input codes used by ``%1INPT`` / ``%2INPT``."""

    HOME = "30"
    HDMI1 = "31"
    HDMI2 = "32"
    HDMI3 = "33"


class MuteState(StrEnum):
    """Audio mute codes used by ``%1AVMT`` (audio only on Valerion)."""

    MUTED = "21"
    UNMUTED = "20"


class RemoteKey(StrEnum):
    """Remote key codes used by ``%3RCNC``."""

    UP = "0"
    DOWN = "1"
    LEFT = "2"
    RIGHT = "3"
    OK = "4"
    RETURN = "5"
    MENU = "6"
    SETTINGS = "7"
    HOME = "8"


class EnhancedBlackLevel(StrEnum):
    """``%3ENBL`` values."""

    OFF = "0"
    LOW = "1"
    MEDIUM = "2"
    HIGH = "3"


class MotionEnhancement(StrEnum):
    """``%3MOTN`` values (Response Data sheet)."""

    OFF = "0"
    CUSTOM = "1"
    FILM = "2"
    CLEAR = "3"
    STANDARD = "4"
    SMOOTH = "5"


class Gamma(StrEnum):
    """``%3GAMA`` values. 4 and 5 are reported in HDR but cannot be set."""

    GAMMA_2_0 = "0"
    GAMMA_2_2 = "1"
    GAMMA_2_4 = "2"
    BT1886 = "3"
    SMPTE2084 = "4"
    HLG = "5"


SETTABLE_GAMMA: Final = (Gamma.GAMMA_2_0, Gamma.GAMMA_2_2, Gamma.GAMMA_2_4, Gamma.BT1886)


class DynamicToneMapping(StrEnum):
    """``%3DYTM`` values (HDR10 only)."""

    OFF = "0"
    LOW = "1"
    HIGH = "2"


class ColorTemperature(StrEnum):
    """``%3CLTP`` values."""

    WARM1 = "0"
    WARM2 = "1"
    STANDARD = "2"
    COOL = "3"


class AspectRatio(StrEnum):
    """``%3ASPR`` values (query only in the official command list)."""

    AUTO = "0"
    RATIO_4_3 = "1"
    ZOOM = "2"
    RATIO_16_9 = "3"
    RATIO_21_9 = "4"
    RATIO_32_9 = "5"
    ANAMORPHIC_16_9 = "6"
    ANAMORPHIC_2_39_1 = "7"
    ANAMORPHIC_1_85_1 = "8"
    ANAMORPHIC_2_0_1 = "9"


class LedStatus(StrEnum):
    """``%3LEDS`` values."""

    NORMAL = "0"
    OVERTEMPERATURE = "1"
    OPEN_CIRCUIT = "2"
    FAN_ERROR = "3"
    STARTUP_ERROR = "4"
    OBSTACLE_DETECTION = "6"


class ErrorStatus(StrEnum):
    """``%2ERST`` values."""

    NORMAL = "0"
    OVERTEMPERATURE = "1"
    OPEN_CIRCUIT = "2"
    FAN_ERROR = "3"
    STARTUP_ERROR = "4"


LASER_LEVEL_MIN: Final = 0
LASER_LEVEL_MAX: Final = 10
VOLUME_MIN: Final = 0
VOLUME_MAX: Final = 100

#: Picture mode names documented by AWOL. The projector only accepts the
#: names that match the current signal format; ``%3PICL ?`` lists them.
PICTURE_MODES_SDR: Final = (
    "Standard",
    "Vivid",
    "Sports",
    "Energy Saving",
    "PC/Game",
    "Theater",
    "FILMMAKER MODE",
)
PICTURE_MODES_HDR: Final = (
    "HDR Standard",
    "HDR Vivid",
    "HDR Sports",
    "HDR Energy Saving",
    "HDR Game",
    "HDR Theater",
    "IMAX Mode",
)
PICTURE_MODES_HDR10_PLUS: Final = (
    "HDR10+ Standard",
    "HDR10+ Vivid",
    "HDR10+ Game",
    "HDR10+ Theater",
)
PICTURE_MODES_DOLBY_VISION: Final = (
    "Dolby Vision Bright",
    "Dolby Vision Dark",
    "Dolby Vision Custom",
    "Dolby Vision Game",
)
ALL_PICTURE_MODES: Final = (
    *PICTURE_MODES_SDR,
    *PICTURE_MODES_HDR,
    *PICTURE_MODES_HDR10_PLUS,
    *PICTURE_MODES_DOLBY_VISION,
)

MODELS: Final = (
    "VisionMaster Plus",
    "VisionMaster Plus2",
    "VisionMaster Pro",
    "VisionMaster Pro2",
    "VisionMaster Max",
)

NO_SIGNAL: Final = "-"
UNKNOWN_SIGNAL: Final = "*"
NO_SIGNAL_INFO: Final = "255"


def split_multi_value(value: str) -> list[str]:
    """Split a multi-value reply such as ``%3FANS`` or ``%3SINF``.

    The official sheet shows the fields on separate lines; some firmware may
    use spaces or commas instead. Until the format is confirmed on real
    hardware we accept any of them and drop empty parts.
    """
    for separator in ("\n", "\r", ",", ";"):
        if separator in value:
            return [part.strip() for part in value.split(separator) if part.strip()]
    return [part for part in value.split(" ") if part]


def split_picture_mode_list(value: str) -> list[str]:
    """Split ``%3PICL ?`` into mode names.

    Mode names contain spaces ("HDR Theater"), so a plain space split is
    wrong. Commas and newlines are tried first; as a last resort the known
    mode names are matched greedily against the text.
    """
    for separator in ("\n", "\r", ",", ";", "|"):
        if separator in value:
            return [part.strip() for part in value.split(separator) if part.strip()]
    text = value.strip()
    if not text:
        return []
    if text in ALL_PICTURE_MODES:
        return [text]
    found: list[str] = []
    remaining = text
    for mode in sorted(ALL_PICTURE_MODES, key=len, reverse=True):
        if mode in remaining:
            found.append(mode)
            remaining = remaining.replace(mode, " ")
    if found:
        return [mode for mode in ALL_PICTURE_MODES if mode in found]
    return [text]


@dataclass(frozen=True, slots=True)
class SignalInfo:
    """Parsed ``%3SINF ?`` reply.

    Field order follows the official sheet: video format, audio format,
    colour depth, colour format, HDR format, colour space. Fields that are
    missing are ``None``. ``raw`` always keeps the untouched value.
    """

    raw: str
    video_format: str | None = None
    audio_format: str | None = None
    color_depth: str | None = None
    color_format: str | None = None
    hdr_format: str | None = None
    color_space: str | None = None

    @classmethod
    def parse(cls, value: str) -> SignalInfo:
        """Parse a raw ``%3SINF`` value."""
        if value.strip() in ("", NO_SIGNAL_INFO):
            return cls(raw=value)
        parts = split_multi_value(value)
        cleaned = [_strip_label(part) for part in parts]
        padded = (cleaned + [None] * 6)[:6]
        return cls(
            raw=value,
            video_format=padded[0],
            audio_format=padded[1],
            color_depth=padded[2],
            color_format=padded[3],
            hdr_format=padded[4],
            color_space=padded[5],
        )


def _strip_label(part: str) -> str | None:
    """Turn ``"HDR format: HDR10"`` into ``"HDR10"``; keep bare values."""
    for colon in (":", "："):  # noqa: RUF001 - the sheet uses a fullwidth colon
        if colon in part:
            label, _, rest = part.partition(colon)
            if label.strip() and rest.strip():
                return rest.strip()
    return part.strip() or None


@dataclass(frozen=True, slots=True)
class DeviceIdentity:
    """Static information, read whenever the projector starts answering."""

    manufacturer: str | None = None
    model: str | None = None
    name: str | None = None
    #: Raw ``%2SVER`` reply, for example ``"V02.01.00E.Q0718 83 OEM01.0.0.0"``.
    software_version: str | None = None
    pjlink_class: str | None = None
    color: str | None = None
    inputs: tuple[str, ...] = field(default_factory=tuple)
    recommended_resolution: str | None = None

    @property
    def firmware(self) -> str | None:
        """Return only the firmware version, the first field of ``%2SVER``.

        The second field differs between on (``83``) and standby (``00``) on
        the Pro2, so it must not be shown as part of the version.
        """
        parts = (self.software_version or "").split()
        return parts[0] if parts else None
