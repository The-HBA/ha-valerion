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
from .locks import KNOWN_3D_LOCKS, KNOWN_LOCKS, LearnedLock, LockTable
from .models import (
    ALL_PICTURE_MODES,
    LASER_LEVEL_MAX,
    LASER_LEVEL_MIN,
    MODELS,
    SETTABLE_GAMMA,
    VOLUME_MAX,
    VOLUME_MIN,
    AspectRatio,
    AudioFormat,
    ColorDepth,
    ColorFormat,
    ColorPrimaries,
    ColorTemperature,
    DeviceIdentity,
    DynamicToneMapping,
    EnhancedBlackLevel,
    ErrorStatus,
    Gamma,
    HdrFormat,
    Input,
    LedStatus,
    MotionEnhancement,
    MuteState,
    PowerState,
    RemoteKey,
    SignalInfo,
    VideoTiming,
    parse_number_list,
    split_multi_value,
    split_picture_mode_list,
)
from .notifications import (
    NOTIFICATION_PORT,
    listen_for_notifications,
    local_address_towards,
    resolve_ipv4,
)
from .protocol import AwolLinkProtocolError, Command, Response, parse_command_line
from .wol import DEFAULT_BROADCAST, build_magic_packet, normalize_mac, send_magic_packet

__version__ = "0.1.0"

__all__ = [
    "ALL_PICTURE_MODES",
    "DEFAULT_BROADCAST",
    "DEFAULT_PORT",
    "DEFAULT_TIMEOUT",
    "KEYS",
    "KNOWN_3D_LOCKS",
    "KNOWN_LOCKS",
    "LASER_LEVEL_MAX",
    "LASER_LEVEL_MIN",
    "MODELS",
    "NOTIFICATION_PORT",
    "SETTABLE_GAMMA",
    "VOLUME_MAX",
    "VOLUME_MIN",
    "AspectRatio",
    "AudioFormat",
    "AwolLinkAuthError",
    "AwolLinkClient",
    "AwolLinkCommandError",
    "AwolLinkConnectionError",
    "AwolLinkError",
    "AwolLinkProtocolError",
    "AwolLinkRefusedError",
    "AwolLinkSession",
    "AwolLinkUnresponsiveError",
    "ColorDepth",
    "ColorFormat",
    "ColorPrimaries",
    "ColorTemperature",
    "Command",
    "DeviceIdentity",
    "DiscoveredDevice",
    "DynamicToneMapping",
    "EnhancedBlackLevel",
    "ErrorStatus",
    "Gamma",
    "HdrFormat",
    "Input",
    "KeyPress",
    "LearnedLock",
    "LedStatus",
    "LockTable",
    "MotionEnhancement",
    "MuteState",
    "PowerState",
    "RemoteKey",
    "Response",
    "SignalInfo",
    "VideoTiming",
    "__version__",
    "build_magic_packet",
    "discover",
    "key_press",
    "listen_for_notifications",
    "local_address_towards",
    "normalize_mac",
    "parse_command_line",
    "parse_number_list",
    "protocol",
    "resolve_ipv4",
    "send_magic_packet",
    "split_multi_value",
    "split_picture_mode_list",
]
