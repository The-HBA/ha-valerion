"""Wake-on-LAN magic packet sender (asyncio, dependency free).

A projector in standby accepts TCP connections but never answers, so the
only way to power it on over the network is a magic packet to its MAC
address. The projector cannot report its own MAC over AWOL Link (the UDP
search reply carries its network name instead); the user reads it from
All Settings > System > About > Status.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Sequence

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
    targets: Sequence[str] = (DEFAULT_BROADCAST,),
    port: int = DEFAULT_PORT,
    repeats: int = _REPEATS,
) -> list[str]:
    """Send the magic packet for ``mac`` to every address in ``targets``.

    A broadcast only reaches the sender's own subnet. A unicast to the
    projector's IP also crosses a router (another VLAN) as long as the router
    still knows the projector's MAC, so callers usually pass both. Host names
    are resolved first; a target that cannot be resolved or sent to is
    skipped. The packet is sent ``repeats`` times because UDP is best effort
    and Wi-Fi receivers in power-save mode drop frames.

    Returns the addresses the packet was sent to. Raises ``OSError`` if it
    could not be sent to any of them.
    """
    packet = build_magic_packet(mac)
    loop = asyncio.get_running_loop()
    addresses: list[str] = []
    last_error: OSError | None = None
    for target in targets:
        try:
            address = await _resolve(loop, target)
        except OSError as err:
            last_error = err
            continue
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise last_error or OSError("no Wake-on-LAN target")
    transport, _ = await loop.create_datagram_endpoint(
        asyncio.DatagramProtocol,
        family=socket.AF_INET,
        allow_broadcast=True,
    )
    sent: list[str] = []
    try:
        for attempt in range(repeats):
            for address in addresses:
                try:
                    transport.sendto(packet, (address, port))
                except OSError as err:
                    last_error = err
                    continue
                if attempt == 0:
                    sent.append(address)
            await asyncio.sleep(0.05)
    finally:
        transport.close()
    if not sent:
        raise last_error or OSError("Wake-on-LAN packet not sent")
    return sent


async def _resolve(loop: asyncio.AbstractEventLoop, target: str) -> str:
    """Return ``target`` as an IPv4 address, resolving host names without blocking."""
    try:
        return str(ipaddress.IPv4Address(target))
    except ValueError:
        pass
    infos = await loop.getaddrinfo(target, None, family=socket.AF_INET, type=socket.SOCK_DGRAM)
    if not infos:
        msg = f"cannot resolve {target!r}"
        raise OSError(msg)
    return str(infos[0][4][0])
