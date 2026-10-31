"""Tests for the asyncio client against the fake projector."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

from custom_components.valerion.lib import (
    AwolLinkAuthError,
    AwolLinkClient,
    AwolLinkCommandError,
    AwolLinkConnectionError,
    AwolLinkRefusedError,
    AwolLinkUnresponsiveError,
    protocol,
)

from .fake_projector import FakeProjector


def _client(fake: FakeProjector, **kwargs: object) -> AwolLinkClient:
    return AwolLinkClient("127.0.0.1", fake.port, timeout=1.0, **kwargs)  # type: ignore[arg-type]


async def test_probe_reads_greeting_and_disconnects(projector: FakeProjector) -> None:
    client = _client(projector)
    assert await client.probe() == "PJLINK 0 "
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


async def test_unknown_class3_query_raises_err1(projector: FakeProjector) -> None:
    # The Pro2 answers "%3ZZZZ ?" with "%3ZZZZ?=ERR1"; it must not time out.
    client = _client(projector)
    async with client.session() as session:
        with pytest.raises(AwolLinkCommandError) as excinfo:
            await session.raw("%3ZZZZ ?")
    assert excinfo.value.error == "ERR1"


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
    # Windows retries a refused localhost connection for about 2 s before giving up.
    client = AwolLinkClient("127.0.0.1", port, timeout=5.0)
    with pytest.raises(AwolLinkRefusedError) as excinfo:
        await client.probe()
    assert isinstance(excinfo.value, AwolLinkConnectionError)
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


@asynccontextmanager
async def _scripted(greeting: bytes | None, *replies: bytes | None) -> AsyncIterator[int]:
    """A TCP server that sends ``greeting``, then one reply per line it receives.

    ``None`` closes the connection at that point instead. After the last reply
    the connection stays open and silent. Yields the port.
    """

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            if greeting is None:
                return
            writer.write(greeting)
            await writer.drain()
            for reply in replies:
                await reader.readuntil(b"\r")
                if reply is None:
                    return
                writer.write(reply)
                await writer.drain()
            await reader.read()
        except ConnectionError, asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    try:
        yield int(server.sockets[0].getsockname()[1])
    finally:
        server.close()
        await server.wait_closed()


def _local(port: int, **kwargs: object) -> AwolLinkClient:
    return AwolLinkClient("127.0.0.1", port, timeout=0.3, **kwargs)  # type: ignore[arg-type]


async def test_client_as_context_manager(projector: FakeProjector) -> None:
    async with _client(projector) as client:
        assert await client.query(protocol.POWER) == "1"


async def test_empty_and_unparsable_lines_are_skipped() -> None:
    async with _scripted(b"PJLINK 0\r", b"\rnot a reply\r%1POWR=1\r") as port:
        assert await _local(port).query(protocol.POWER) == "1"


async def test_set_answered_without_ok_is_accepted() -> None:
    async with _scripted(b"PJLINK 0\r", b"%3LASL=5\r") as port:
        await _local(port).send(protocol.LASER_LEVEL, 5)


async def test_too_many_unrelated_lines(projector: FakeProjector) -> None:
    projector.unsolicited.extend(["%2ERST=0"] * 10)
    with pytest.raises(AwolLinkConnectionError, match="10 unrelated lines"):
        await _client(projector).query(protocol.POWER)


async def test_no_reply_in_time(projector: FakeProjector) -> None:
    projector.reply_delay = 0.5
    with pytest.raises(AwolLinkConnectionError, match="no reply"):
        await _local(projector.port).query(protocol.POWER)


async def test_connection_lost_while_waiting() -> None:
    async with _scripted(b"PJLINK 0\r", None) as port:
        with pytest.raises(AwolLinkConnectionError, match="connection lost"):
            await _local(port).query(protocol.POWER)


async def test_auth_failure_during_a_session() -> None:
    async with _scripted(b"PJLINK 0\r", b"PJLINK ERRA\r") as port:
        with pytest.raises(AwolLinkAuthError):
            await _local(port).query(protocol.POWER)


@pytest.mark.parametrize(
    ("greeting", "error"),
    [
        (None, AwolLinkConnectionError),  # closed before greeting
        (b"HELLO\r", protocol.AwolLinkProtocolError),
        (b"PJLINK ERRA\r", AwolLinkAuthError),
    ],
)
async def test_bad_greetings(greeting: bytes | None, error: type[Exception]) -> None:
    async with _scripted(greeting) as port:
        with pytest.raises(error):
            await _local(port, security_code="1234").probe()


async def test_no_answer_to_the_digest() -> None:
    # Silence is "not answering", not a wrong code (that would start a reauth).
    async with _scripted(b"PJLINK 1 498e4a67\r") as port:
        with pytest.raises(AwolLinkUnresponsiveError, match="no answer"):
            await _local(port, security_code="1234").probe()


async def test_connection_closed_during_authentication() -> None:
    async with _scripted(b"PJLINK 1 498e4a67\r", None) as port:
        with pytest.raises(AwolLinkConnectionError, match="during authentication"):
            await _local(port, security_code="1234").probe()


async def test_connect_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    async def hang(*args: object) -> None:
        await asyncio.sleep(1)

    monkeypatch.setattr(asyncio, "open_connection", hang)
    with pytest.raises(AwolLinkConnectionError, match="timeout connecting"):
        await AwolLinkClient("192.0.2.1", timeout=0.05).probe()


async def test_connect_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(*args: object) -> None:
        raise OSError("no route to host")

    monkeypatch.setattr(asyncio, "open_connection", fail)
    with pytest.raises(AwolLinkConnectionError, match="no route to host") as excinfo:
        await AwolLinkClient("192.0.2.1").probe()
    assert not isinstance(excinfo.value, AwolLinkRefusedError)
