"""Constants for the Valerion integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "valerion"
NAME: Final = "Valerion"
MANUFACTURER: Final = "Valerion (AWOL Vision)"

CONF_SECURITY_CODE: Final = "security_code"
CONF_POWER_OFF_MODE: Final = "power_off_mode"
CONF_BROADCAST_ADDRESS: Final = "broadcast_address"
CONF_BROADCAST_PORT: Final = "broadcast_port"

POWER_OFF_MODE_STANDBY: Final = "standby"
POWER_OFF_MODE_FULL: Final = "full"
DEFAULT_POWER_OFF_MODE: Final = POWER_OFF_MODE_STANDBY

#: Poll every 30 s while the projector is off, in standby or unreachable.
INTERVAL_IDLE: Final = timedelta(seconds=30)
#: Poll every 10 s while the projector is on.
INTERVAL_ON: Final = timedelta(seconds=10)
#: Poll every 2 s while waiting for a power transition to finish.
INTERVAL_TRANSITION: Final = timedelta(seconds=2)
#: Slow-tier settings are refreshed every N "on" polls (about once a minute).
SLOW_TIER_EVERY: Final = 6
#: Silent polls tolerated before an "on" projector is considered in standby.
SILENT_POLLS_BEFORE_STANDBY: Final = 3
#: How long turn_on keeps retrying after the Wake-on-LAN packet.
POWER_ON_TIMEOUT: Final = timedelta(seconds=45)
POWER_ON_RETRY: Final = timedelta(seconds=2)
#: How often turn_on repeats the Wake-on-LAN packet while it waits.
WOL_RESEND: Final = timedelta(seconds=6)

SOURCE_NAMES: Final[dict[str, str]] = {
    "30": "Home",
    "31": "HDMI 1",
    "32": "HDMI 2",
    "33": "HDMI 3",
}
