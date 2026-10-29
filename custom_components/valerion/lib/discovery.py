"""UDP discovery helpers (``%2SRCH`` / ``%2ACKN``).

The official command list documents a UDP search on port 4352. The reply
format (``%2ACKN=<value>``) is only loosely described, so everything here
returns raw text and the caller decides what to do with it.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import socket
from typing import Final

from .protocol import SEARCH, AwolLinkProtocolError, decode_line, encode_line, parse_response

DEFAULT_PORT: Final = 4352
BROADCAST: Final = "255.255.255.255"


@dataclass(frozen=True, slots=True)
class DiscoveredDevice:
    """One UDP answer to the search command."""

    host: str
    raw: str
    code: str
    value: str


class _Collector(asyncio.DatagramProtocol):
    def __init__(self) -> None:
        self.found: list[DiscoveredDevice] = []

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            text = decode_line(data)
            response = parse_response(text)
        except AwolLinkProtocolError:
            return
        self.found.append(
            DiscoveredDevice(host=addr[0], raw=text, code=response.code, value=response.value)
        )


async def discover(
    target: str = BROADCAST,
    *,
    port: int = DEFAULT_PORT,
    wait: float = 2.0,
) -> list[DiscoveredDevice]:
    """Send ``%2SRCH`` to ``target`` and collect answers for ``wait`` seconds.

    ``target`` may be the broadcast address (same subnet only) or a single
    projector IP, which also works through a routed VPN.
    """
    loop = asyncio.get_running_loop()
    collector = _Collector()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: collector,
        local_addr=("0.0.0.0", 0),  # noqa: S104 - we must listen for the reply
        family=socket.AF_INET,
        allow_broadcast=True,
    )
    try:
        transport.sendto(encode_line(SEARCH.header), (target, port))
        await asyncio.sleep(wait)
    finally:
        transport.close()
    return collector.found
