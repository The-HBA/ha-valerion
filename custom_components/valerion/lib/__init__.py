"""AWOL Link protocol library for Valerion (AWOL Vision) projectors.

This package has no Home Assistant dependency. It can be used on its own
(see ``cli.py``) and is written so that it can later be published to PyPI
without changes.
"""

from __future__ import annotations

from . import protocol
from .client import DEFAULT_PORT, DEFAULT_TIMEOUT, AwolLinkClient, AwolLinkSession
from .discovery import DiscoveredDevice, discover
from .exceptions import (
    AwolLinkAuthError,
    AwolLinkCommandError,
    AwolLinkConnectionError,
    AwolLinkError,
    AwolLinkRefusedError,
    AwolLinkUnresponsiveError,
)
from .keys import KEYS, KeyPress, key_press
from .models import (
    ALL_PICTURE_MODES,
    LASER_LEVEL_MAX,
    LASER_LEVEL_MIN,
    MODELS,
    SETTABLE_GAMMA,
    VOLUME_MAX,
    VOLUME_MIN,
    AspectRatio,
    ColorTemperature,
    DeviceIdentity,
    DynamicToneMapping,
    EnhancedBlackLevel,
    ErrorStatus,
    Gamma,
    Input,
    LedStatus,
    MotionEnhancement,
    MuteState,
    PowerState,
    RemoteKey,
    SignalInfo,
    split_multi_value,
    split_picture_mode_list,
)
from .protocol import AwolLinkProtocolError, Command, Response, parse_command_line
from .wol import build_magic_packet, normalize_mac, send_magic_packet

__version__ = "0.0.7"

__all__ = [
    "ALL_PICTURE_MODES",
    "DEFAULT_PORT",
    "DEFAULT_TIMEOUT",
    "KEYS",
    "LASER_LEVEL_MAX",
    "LASER_LEVEL_MIN",
    "MODELS",
    "SETTABLE_GAMMA",
    "VOLUME_MAX",
    "VOLUME_MIN",
    "AspectRatio",
    "AwolLinkAuthError",
    "AwolLinkClient",
    "AwolLinkCommandError",
    "AwolLinkConnectionError",
    "AwolLinkError",
    "AwolLinkProtocolError",
    "AwolLinkRefusedError",
    "AwolLinkSession",
    "AwolLinkUnresponsiveError",
    "ColorTemperature",
    "Command",
    "DeviceIdentity",
    "DiscoveredDevice",
    "DynamicToneMapping",
    "EnhancedBlackLevel",
    "ErrorStatus",
    "Gamma",
    "Input",
    "KeyPress",
    "LedStatus",
    "MotionEnhancement",
    "MuteState",
    "PowerState",
    "RemoteKey",
    "Response",
    "SignalInfo",
    "__version__",
    "build_magic_packet",
    "discover",
    "key_press",
    "normalize_mac",
    "parse_command_line",
    "protocol",
    "send_magic_packet",
    "split_multi_value",
    "split_picture_mode_list",
]
