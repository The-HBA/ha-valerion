"""Tests for the Status Notification listener, with real UDP packets on 127.0.0.1."""

from __future__ import annotations

import asyncio
import socket

import pytest

from custom_components.valerion.lib import (
    Response,
    listen_for_notifications,
    local_address_towards,
    resolve_ipv4,
)


def _send(port: int, data: bytes) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
        sender.sendto(data, ("127.0.0.1", port))


async def test_listener_passes_on_messages_and_drops_the_rest() -> None:
    received: asyncio.Queue[tuple[str, Response]] = asyncio.Queue()
    transport = await listen_for_notifications(
        lambda sender, message: received.put_nowait((sender, message)), port=0
    )
    port = transport.get_extra_info("sockname")[1]
    try:
        _send(port, b"not a message\r")
        _send(port, b"\xff\xfe\r")
        # Measured on the Pro2: each message ends in a carriage return.
        _send(port, b"%2POWR=0\r")

        sender, message = await asyncio.wait_for(received.get(), 2)
    finally:
        transport.close()
    assert sender == "127.0.0.1"
    assert message.header == "%2POWR"
    assert message.value == "0"
    assert received.empty()


async def test_listener_reports_a_port_in_use() -> None:
    transport = await listen_for_notifications(lambda _sender, _message: None, port=0)
    port = transport.get_extra_info("sockname")[1]
    try:
        with pytest.raises(OSError, match="in use"):
            await listen_for_notifications(lambda _sender, _message: None, port=port)
    finally:
        transport.close()


async def test_resolve_ipv4() -> None:
    assert await resolve_ipv4("127.0.0.1") == {"127.0.0.1"}


async def test_resolve_ipv4_of_an_unknown_name(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(*_args: object, **_kwargs: object) -> list[object]:
        raise socket.gaierror

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", fail)
    assert await resolve_ipv4("projector.invalid") == set()


def test_local_address_towards() -> None:
    assert local_address_towards("127.0.0.1") == "127.0.0.1"


def test_local_address_towards_without_a_route(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_args: object) -> None:
        raise OSError

    monkeypatch.setattr(socket.socket, "connect", fail)
    assert local_address_towards("127.0.0.1") is None
