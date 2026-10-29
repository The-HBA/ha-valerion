"""Tests for the Wake-on-LAN helper."""

from __future__ import annotations

import asyncio
import socket

import pytest

from custom_components.valerion.lib import build_magic_packet, normalize_mac, send_magic_packet


@pytest.mark.parametrize(
    "raw",
    [
        "AA:BB:CC:DD:EE:FF",
        "aa-bb-cc-dd-ee-ff",
        "aabb.ccdd.eeff",
        "AABBCCDDEEFF",
        " aa:bb:cc:dd:ee:ff ",
    ],
)
def test_normalize_mac(raw: str) -> None:
    assert normalize_mac(raw) == "aa:bb:cc:dd:ee:ff"


@pytest.mark.parametrize("raw", ["", "AA:BB:CC", "zz:bb:cc:dd:ee:ff", "aabbccddeeff00"])
def test_normalize_mac_rejects_garbage(raw: str) -> None:
    with pytest.raises(ValueError, match="invalid MAC"):
        normalize_mac(raw)


def test_build_magic_packet() -> None:
    packet = build_magic_packet("aa:bb:cc:dd:ee:ff")
    assert len(packet) == 102
    assert packet[:6] == b"\xff" * 6
    assert packet[6:12] == bytes.fromhex("aabbccddeeff")
    assert packet[6:] == bytes.fromhex("aabbccddeeff") * 16


async def test_send_magic_packet_reaches_a_udp_socket() -> None:
    loop = asyncio.get_running_loop()
    received: asyncio.Future[bytes] = loop.create_future()

    class _Sink(asyncio.DatagramProtocol):
        def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
            if not received.done():
                received.set_result(data)

    transport, _ = await loop.create_datagram_endpoint(
        _Sink, local_addr=("127.0.0.1", 0), family=socket.AF_INET
    )
    port = transport.get_extra_info("sockname")[1]
    try:
        await send_magic_packet("aa:bb:cc:dd:ee:ff", broadcast="127.0.0.1", port=port, repeats=1)
        data = await asyncio.wait_for(received, 2)
    finally:
        transport.close()
    assert data == build_magic_packet("aa:bb:cc:dd:ee:ff")
