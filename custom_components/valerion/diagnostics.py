"""Diagnostics support for the Valerion integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC

from .const import CONF_SECURITY_CODE

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .coordinator import ValerionConfigEntry
    from .lib import SignalInfo

TO_REDACT = {CONF_HOST, CONF_MAC, CONF_SECURITY_CODE, "unique_id", "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ValerionConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "unique_id": entry.unique_id,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            TO_REDACT,
        ),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
            "last_greeting": coordinator.client.last_greeting,
        },
        "state": {
            "connection": data.connection,
            "power": data.power,
            "busy": data.busy,
            "values": data.values,
            "unavailable": sorted(data.unavailable),
            "locked": sorted(data.locked),
            "identity": asdict(data.identity),
            "signal": _signal(data.signal),
            "picture_modes": list(data.picture_modes),
            "last_error": data.last_error,
        },
        "learned_locks": coordinator.locks_as_dict(),
    }


def _signal(signal: SignalInfo | None) -> dict[str, Any] | None:
    """Return the raw signal fields plus how they were decoded."""
    if signal is None:
        return None
    return {
        **asdict(signal),
        "decoded": {
            "has_signal": signal.has_signal,
            "timing": str(signal.timing) if signal.timing else None,
            "audio": signal.audio,
            "depth": signal.depth,
            "chroma": signal.chroma,
            "hdr": signal.hdr,
            "primaries": signal.primaries,
        },
    }
