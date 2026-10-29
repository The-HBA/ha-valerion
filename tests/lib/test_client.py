"""Tests for the asyncio client against the fake projector."""

from __future__ import annotations

import asyncio

import pytest

from custom_components.valerion.lib import (
    AwolLinkAuthError,
    AwolLinkClient,
    AwolLinkCommandError,
    AwolLinkConnectionError,
    AwolLinkUnresponsiveError,
    protocol,
)

from .fake_projector import FakeProjector


def _client(fake: FakeProjector, **kwargs: object) -> AwolLinkClient:
    return AwolLinkClient("127.0.0.1", fake.port, timeout=1.0, **kwargs)  # type: ignore[arg-type]


async def test_probe_reads_greeting_and_disconnects(projector: FakeProjector) -> None:
    client = _client(projector)
    assert await client.probe() == "PJLINK 0"
    assert projector.connections == 1
    assert projector.greeted == 1


async def test_query_and_send_in_one_session(projector: FakeProjector) -> None:
    client = _client(projector)
    async with client.session() as session:
        assert await session.query(protocol.POWER) == "1"
        await session.send(protocol.LASER_LEVEL, 3)
        assert await session.query(protocol.LASER_LEVEL) == "3"
        assert session.last_round_trip is not None
    assert projector.connections == 1
    assert projector.received == ["%1POWR ?", "%3LASL 3", "%3LASL ?"]


async def test_convenience_methods_open_separate_sessions(projector: FakeProjector) -> None:
    client = _client(projector)
    assert await client.query(protocol.MODEL) == "VisionMaster Pro2"
    await client.send(protocol.VOLUME, 50)
    assert projector.values["%3VOLM"] == "50"
    assert projector.connections == 2


async def test_query_many_collects_errors(projector: FakeProjector) -> None:
    projector.unavailable.add("%3GAMA")
    client = _client(projector)
    async with client.session() as session:
        results = await session.query_many(
            [protocol.POWER, protocol.GAMMA, protocol.DYNAMIC_TONE_MAPPING]
        )
    assert results["POWR"] == "1"
    gamma = results["GAMA"]
    assert isinstance(gamma, AwolLinkCommandError)
    assert gamma.is_unavailable
    dytm = results["DYTM"]
    assert isinstance(dytm, AwolLinkCommandError)
    assert dytm.error == "ERR1"


async def test_set_error_raises_command_error(projector: FakeProjector) -> None:
    client = _client(projector)
    with pytest.raises(AwolLinkCommandError) as excinfo:
        await client.send(protocol.GAMMA, 9)
    assert excinfo.value.error == "ERR1"
    assert "%3GAMA 9" in str(excinfo.value)


async def test_security_code_handshake(secured_projector: FakeProjector) -> None:
    client = _client(secured_projector, security_code="1234")
    assert await client.query(protocol.POWER) == "1"
    assert secured_projector.greeted == 1


async def test_wrong_security_code(secured_projector: FakeProjector) -> None:
    client = _client(secured_projector, security_code="0000")
    with pytest.raises(AwolLinkAuthError):
        await client.probe()


async def test_missing_security_code(secured_projector: FakeProjector) -> None:
    client = _client(secured_projector)
    with pytest.raises(AwolLinkAuthError):
        await client.probe()


async def test_silent_projector_is_reported_as_unresponsive() -> None:
    fake = FakeProjector(silent=True)
    await fake.start()
    try:
        client = AwolLinkClient("127.0.0.1", fake.port, timeout=0.3)
        with pytest.raises(AwolLinkUnresponsiveError):
            await client.probe()
    finally:
        await fake.stop()


async def test_connection_refused() -> None:
    fake = FakeProjector()
    await fake.start()
    port = fake.port
    await fake.stop()
    client = AwolLinkClient("127.0.0.1", port, timeout=0.5)
    with pytest.raises(AwolLinkConnectionError) as excinfo:
        await client.probe()
    assert not isinstance(excinfo.value, AwolLinkUnresponsiveError)


async def test_unsolicited_lines_are_skipped_and_reported(projector: FakeProjector) -> None:
    seen: list[str] = []
    projector.unsolicited.append("%2ERST=0")
    client = _client(projector, on_unsolicited=lambda r: seen.append(r.raw))
    assert await client.query(protocol.POWER) == "1"
    assert seen == ["%2ERST=0"]


async def test_sessions_are_serialised(projector: FakeProjector) -> None:
    projector.reply_delay = 0.05
    client = _client(projector)

    async def one() -> str:
        return await client.query(protocol.POWER)

    results = await asyncio.gather(one(), one(), one())
    assert results == ["1", "1", "1"]
    assert projector.connections == 3


async def test_repr_hides_security_code(projector: FakeProjector) -> None:
    client = _client(projector, security_code="secret")
    assert "secret" not in repr(client)
