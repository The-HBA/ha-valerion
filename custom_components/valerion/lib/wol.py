"""Wake-on-LAN magic packet sender (asyncio, dependency free).

A projector in standby accepts TCP connections but never answers, so the
only way to power it on over the network is a magic packet to its MAC
address. The projector cannot report its own MAC over AWOL Link; the user
reads it from All Settings > System > About > Status.
"""

from __future__ import annotations

import asyncio
import re
import socket
from typing import Final

DEFAULT_BROADCAST: Final = "255.255.255.255"
DEFAULT_PORT: Final = 9
_MAC_RE: Final = re.compile(r"^[0-9A-Fa-f]{12}$")
_REPEATS: Final = 3


def normalize_mac(mac: str) -> str:
    """Return ``mac`` as lowercase ``aa:bb:cc:dd:ee:ff``.

    Accepts separators ``:``, ``-`` and ``.`` or no separator at all.
    Raises ``ValueError`` for anything that is not 12 hexadecimal digits.
    """
    digits = re.sub(r"[:\-. ]", "", mac.strip())
    if not _MAC_RE.match(digits):
        msg = f"invalid MAC address: {mac!r}"
        raise ValueError(msg)
    digits = digits.lower()
    return ":".join(digits[i : i + 2] for i in range(0, 12, 2))


def build_magic_packet(mac: str) -> bytes:
    """Return the 102-byte magic packet for ``mac``."""
    payload = bytes.fromhex(normalize_mac(mac).replace(":", ""))
    return b"\xff" * 6 + payload * 16


async def send_magic_packet(
    mac: str,
    *,
    broadcast: str = DEFAULT_BROADCAST,
    port: int = DEFAULT_PORT,
    repeats: int = _REPEATS,
) -> None:
    """Send the magic packet for ``mac`` to ``broadcast``:``port``.

    The packet is sent ``repeats`` times because UDP is best effort and
    Wi-Fi receivers in power-save mode drop frames.
    """
    packet = build_magic_packet(mac)
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        asyncio.DatagramProtocol,
        family=socket.AF_INET,
        allow_broadcast=True,
    )
    try:
        for _ in range(repeats):
            transport.sendto(packet, (broadcast, port))
            await asyncio.sleep(0.05)
    finally:
        transport.close()
