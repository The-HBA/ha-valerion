"""Exceptions raised by the AWOL Link client."""

from __future__ import annotations

from .protocol import ERR_UNAVAILABLE, ERROR_CODES


class AwolLinkError(Exception):
    """Base class for all AWOL Link errors."""


class AwolLinkConnectionError(AwolLinkError):
    """The projector could not be reached over TCP (refused, unroutable, timeout)."""


class AwolLinkRefusedError(AwolLinkConnectionError):
    """The projector refused the TCP connection.

    The projector is on the network but AWOL Link is switched off
    (All Settings > Inputs > External Inputs > AWOL Link).
    """


class AwolLinkUnresponsiveError(AwolLinkConnectionError):
    """TCP connected but the projector never sent its greeting.

    This happens in standby (the network stack accepts connections but the
    control service is asleep) and while another controller holds the single
    control session.
    """


class AwolLinkAuthError(AwolLinkError):
    """The security code was rejected or is required but missing."""


class AwolLinkCommandError(AwolLinkError):
    """The projector answered a command with an ``ERRx`` code."""

    def __init__(self, command: str, error: str) -> None:
        """Initialize with the command line that failed and the error code."""
        self.command = command
        self.error = error
        super().__init__(f"{command}: {ERROR_CODES.get(error, error)} ({error})")

    @property
    def is_unavailable(self) -> bool:
        """Return True for ERR3: the setting is locked in the current state."""
        return self.error == ERR_UNAVAILABLE
