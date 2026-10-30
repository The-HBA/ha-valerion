"""Value enumerations and data models for AWOL Link.

The numeric codes come from the "Response Data" sheet of the official AWOL
Link command list, which is the authoritative source where the two sheets
disagree (motion enhancement).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
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
    """``%3ASPR`` values (setting them is not in the official list; see docs/protocol.md)."""

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


# The ``%3SINF`` code tables below are not in the official command list. AWOL
# support sent them to Michael Konieczki (VMote) on 2026-10-29; they match
# every reply recorded on the Pro2 (docs/protocol.md). ``255`` means
# "unavailable" in every field.


class AudioFormat(StrEnum):
    """Second ``%3SINF`` field. ``MULTI`` means several audio tracks, not multichannel."""

    PCM = "0"
    AAC = "1"
    HE_AAC = "2"
    DOLBY_AUDIO = "3"
    DOLBY_ATMOS = "4"
    DTS = "5"
    DTS_HD = "6"
    DTS_X = "7"
    MP3 = "8"
    FLAC = "9"
    WMA = "10"
    MPEG = "11"
    OTHER = "12"
    MULTI = "13"


class ColorDepth(StrEnum):
    """Third ``%3SINF`` field."""

    BIT_6 = "0"
    BIT_8 = "1"
    BIT_10 = "2"
    BIT_12 = "3"
    BIT_16 = "4"


class ColorFormat(StrEnum):
    """Fourth ``%3SINF`` field."""

    YUV_420 = "0"
    YUV_422 = "1"
    YUV_444 = "2"
    RGB = "3"


class HdrFormat(StrEnum):
    """Fifth ``%3SINF`` field."""

    SDR = "0"
    HDR10 = "1"
    HLG = "2"
    HDR10_PLUS = "3"
    DOLBY_VISION = "4"


class ColorPrimaries(StrEnum):
    """Sixth ``%3SINF`` field."""

    BT709 = "0"
    DCI_P3 = "1"
    BT2020 = "2"


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


def parse_number_list(value: str) -> tuple[int | None, ...]:
    """Parse ``%3FANS`` / ``%3TEMP`` slots into numbers.

    The Pro2 replies ``1770 1710 0 0 0 0 0``: one slot per fan or sensor,
    unused slots are ``0``. A slot that is not a number becomes ``None``.
    """
    return tuple(_as_int(part) for part in split_multi_value(value))


def _as_int(part: str) -> int | None:
    try:
        return int(part)
    except ValueError:
        return None


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


_TIMING = re.compile(
    r"(?P<width>\d+)\s*[*xX]\s*(?P<height>\d+)\s*(?P<scan>[pPiI])?\s*@\s*(?P<rate>\d+(?:\.\d+)?)\s*Hz"
)


@dataclass(frozen=True, slots=True)
class VideoTiming:
    """The first ``%3SINF`` field, for example ``3840*2160p@24Hz``."""

    width: int
    height: int
    interlaced: bool
    refresh_rate: float

    @classmethod
    def parse(cls, value: str) -> VideoTiming | None:
        """Parse a timing string; ``None`` if it does not look like one."""
        match = _TIMING.search(value)
        if match is None:
            return None
        return cls(
            width=int(match["width"]),
            height=int(match["height"]),
            interlaced=(match["scan"] or "p").lower() == "i",
            refresh_rate=float(match["rate"]),
        )

    def __str__(self) -> str:
        """Return the timing as text: width, multiplication sign, height, ``p 24 Hz``."""
        scan = "i" if self.interlaced else "p"
        return f"{self.width}×{self.height}{scan} {self.refresh_rate:g} Hz"  # noqa: RUF001


@dataclass(frozen=True, slots=True)
class SignalInfo:
    """Parsed ``%3SINF ?`` reply.

    Fields in order: video timing, audio format, colour depth, colour format,
    HDR format, colour primaries. The text fields keep the raw parts (codes on
    real projectors); the properties decode them. ``raw`` always keeps the
    untouched value.
    """

    raw: str
    video_format: str | None = None
    audio_format: str | None = None
    color_depth: str | None = None
    color_format: str | None = None
    hdr_format: str | None = None
    color_primaries: str | None = None

    @property
    def timing(self) -> VideoTiming | None:
        """Return the decoded video timing, if it can be read."""
        return VideoTiming.parse(self.video_format) if self.video_format else None

    @property
    def has_signal(self) -> bool:
        """Return False for ``255`` (AWOL) and ``0*0p@0Hz`` (Pro2 home screen)."""
        if self.video_format is None:
            return False
        timing = self.timing
        return timing is None or (timing.width > 0 and timing.refresh_rate > 0)

    @property
    def audio(self) -> AudioFormat | None:
        """Return the decoded audio format (``None`` without a signal)."""
        return self._decode(AudioFormat, self.audio_format)

    @property
    def depth(self) -> ColorDepth | None:
        """Return the decoded colour depth."""
        return self._decode(ColorDepth, self.color_depth)

    @property
    def chroma(self) -> ColorFormat | None:
        """Return the decoded colour format."""
        return self._decode(ColorFormat, self.color_format)

    @property
    def hdr(self) -> HdrFormat | None:
        """Return the decoded HDR format."""
        return self._decode(HdrFormat, self.hdr_format)

    @property
    def primaries(self) -> ColorPrimaries | None:
        """Return the decoded colour primaries."""
        return self._decode(ColorPrimaries, self.color_primaries)

    def _decode[E: StrEnum](self, enum: type[E], code: str | None) -> E | None:
        # Without a signal the Pro2 still reports codes (PCM, RGB, SDR); they
        # describe nothing, so they are hidden. Unknown codes become None too.
        if code is None or not self.has_signal:
            return None
        try:
            return enum(code)
        except ValueError:
            return None

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
            color_primaries=padded[5],
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
