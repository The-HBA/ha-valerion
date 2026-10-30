"""Tests for the Wake-on-LAN helper."""

from __future__ import annotations

import asyncio
import socket
from typing import TYPE_CHECKING

import pytest

from custom_components.valerion.lib import build_magic_packet, normalize_mac, send_magic_packet

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


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


class _Sink(asyncio.DatagramProtocol):
    """Collects every datagram sent to a local UDP port."""

    def __init__(self) -> None:
        self.received: list[bytes] = []

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.received.append(data)


@pytest.fixture
async def sink() -> AsyncIterator[tuple[_Sink, int]]:
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        _Sink, local_addr=("127.0.0.1", 0), family=socket.AF_INET
    )
    try:
        yield protocol, transport.get_extra_info("sockname")[1]
    finally:
        transport.close()


async def _wait_for(sink: _Sink, count: int) -> None:
    for _ in range(100):
        if len(sink.received) >= count:
            return
        await asyncio.sleep(0.01)


async def test_send_magic_packet_reaches_a_udp_socket(sink: tuple[_Sink, int]) -> None:
    protocol, port = sink
    sent = await send_magic_packet("aa:bb:cc:dd:ee:ff", targets=["127.0.0.1"], port=port, repeats=1)
    await _wait_for(protocol, 1)
    assert sent == ["127.0.0.1"]
    assert protocol.received == [build_magic_packet("aa:bb:cc:dd:ee:ff")]


async def test_send_magic_packet_resolves_names_and_skips_duplicates(
    sink: tuple[_Sink, int],
) -> None:
    protocol, port = sink
    sent = await send_magic_packet(
        "aa:bb:cc:dd:ee:ff", targets=["127.0.0.1", "localhost"], port=port, repeats=2
    )
    await _wait_for(protocol, 2)
    assert sent == ["127.0.0.1"]
    assert len(protocol.received) == 2


async def test_send_magic_packet_skips_unresolvable_targets(sink: tuple[_Sink, int]) -> None:
    protocol, port = sink
    sent = await send_magic_packet(
        "aa:bb:cc:dd:ee:ff", targets=["no-such-host.invalid", "127.0.0.1"], port=port, repeats=1
    )
    await _wait_for(protocol, 1)
    assert sent == ["127.0.0.1"]
    assert len(protocol.received) == 1


async def test_send_magic_packet_fails_without_any_target() -> None:
    with pytest.raises(OSError):
        await send_magic_packet("aa:bb:cc:dd:ee:ff", targets=["no-such-host.invalid"])
