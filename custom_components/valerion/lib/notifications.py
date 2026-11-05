"""Status Notification: the messages a projector pushes when its status changes.

With an address entered under *AWOL Link > Status Notification*, the projector
sends UDP datagrams such as ``%2POWR=0`` to that address on port 4352. They
carry no authentication, even with a security code set, so a caller should
treat one as a hint to read the projector, never as its state.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import TYPE_CHECKING, Final

from .protocol import AwolLinkProtocolError, Response, decode_line, parse_response

if TYPE_CHECKING:
    from collections.abc import Callable

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_PORT: Final = 4352


class _Receiver(asyncio.DatagramProtocol):
    def __init__(self, on_message: Callable[[str, Response], None]) -> None:
        self._on_message = on_message

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            response = parse_response(decode_line(data))
        except AwolLinkProtocolError:
            _LOGGER.debug("Ignoring a message from %s that is not AWOL Link", addr[0])
            return
        self._on_message(addr[0], response)


async def listen_for_notifications(
    on_message: Callable[[str, Response], None],
    *,
    port: int = NOTIFICATION_PORT,
) -> asyncio.DatagramTransport:
    """Listen on ``port`` and call ``on_message(sender address, message)``.

    Lines that are not AWOL Link are dropped here. Close the returned
    transport to stop. Raises ``OSError`` if the port cannot be opened.
    """
    transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
        lambda: _Receiver(on_message),
        local_addr=("0.0.0.0", port),  # noqa: S104 - the projector sends to this machine
        family=socket.AF_INET,
    )
    return transport


async def resolve_ipv4(host: str) -> set[str]:
    """Return the IPv4 addresses of ``host``, empty if it cannot be resolved."""
    try:
        found = await asyncio.get_running_loop().getaddrinfo(host, None, family=socket.AF_INET)
    except OSError:
        return set()
    return {str(info[4][0]) for info in found}


def local_address_towards(host: str) -> str | None:
    """Return this machine's address on the route to ``host``, or None.

    That is the address to enter on the projector. Nothing is sent: connecting
    a UDP socket only chooses the route. This can block while a name resolves.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect((host, NOTIFICATION_PORT))
            return str(probe.getsockname()[0])
    except OSError:
        return None
