"""Tests for the command line tool and UDP discovery."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
from pathlib import Path
import runpy
import socket
import sys

import pytest

from custom_components.valerion.lib import cli
from custom_components.valerion.lib.discovery import discover
from custom_components.valerion.lib.wol import build_magic_packet

from .fake_projector import FakeProjector

MAC = "aa:bb:cc:dd:ee:ff"


async def _cli(*argv: str) -> int:
    """Run the tool inside the test's event loop (``main`` starts its own)."""
    return await cli._run(cli.build_parser().parse_args(argv))


def _at(fake: FakeProjector, *argv: str) -> tuple[str, ...]:
    return ("--host", "127.0.0.1", "--port", str(fake.port), "--timeout", "1", *argv)


class _Udp(asyncio.DatagramProtocol):
    """Records datagrams on a local UDP port and answers each with ``replies``."""

    def __init__(self, replies: list[bytes]) -> None:
        self.replies = replies
        self.received: list[bytes] = []
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        assert isinstance(transport, asyncio.DatagramTransport)
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.received.append(data)
        assert self.transport is not None
        for reply in self.replies:
            self.transport.sendto(reply, addr)


@pytest.fixture
async def udp() -> AsyncIterator[tuple[_Udp, int]]:
    """A UDP endpoint on 127.0.0.1 that answers like a Pro2 to ``%2SRCH``."""
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: _Udp([b"not a reply\r", b"%2ACKN=VisionMaster Pro2 x GoogleTV2891\r"]),
        local_addr=("127.0.0.1", 0),
        family=socket.AF_INET,
    )
    try:
        yield protocol, transport.get_extra_info("sockname")[1]
    finally:
        transport.close()


def _closed_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def test_probe(projector: FakeProjector, capsys: pytest.CaptureFixture[str]) -> None:
    assert await _cli(*_at(projector, "probe")) == 0
    assert "greeting: 'PJLINK 0 '" in capsys.readouterr().out
    assert projector.connections == 1


async def test_query_known_and_forced_class(
    projector: FakeProjector, capsys: pytest.CaptureFixture[str]
) -> None:
    assert await _cli(*_at(projector, "query", "powr")) == 0
    assert "%1POWR='1'" in capsys.readouterr().out
    projector.values["%2LASL"] = "4"
    assert await _cli(*_at(projector, "query", "LASL", "--class", "2")) == 0
    assert "%2LASL='4'" in capsys.readouterr().out


async def test_query_unknown_code(projector: FakeProjector) -> None:
    with pytest.raises(SystemExit, match="unknown command code 'ZZZZ'"):
        await _cli(*_at(projector, "query", "ZZZZ"))
    assert projector.connections == 0


async def test_set_reads_back(projector: FakeProjector, capsys: pytest.CaptureFixture[str]) -> None:
    assert await _cli(*_at(projector, "set", "LASL", "5")) == 0
    assert "%3LASL 5 -> OK, now '5'" in capsys.readouterr().out
    assert projector.received == ["%3LASL 5", "%3LASL ?"]


async def test_raw(projector: FakeProjector, capsys: pytest.CaptureFixture[str]) -> None:
    assert await _cli(*_at(projector, "raw", "%3PICL ?")) == 0
    assert "'%3PICL=HDR Standard,HDR Vivid,HDR Theater'" in capsys.readouterr().out


async def test_survey_records_replies_and_errors(projector: FakeProjector, tmp_path: Path) -> None:
    out = tmp_path / "survey.json"
    assert await _cli(*_at(projector, "survey", "-o", str(out))) == 0
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["greeting"] == "PJLINK 0 "
    assert document["port"] == projector.port
    results = {entry["command"]: entry for entry in document["results"]}
    assert results["%1POWR ?"]["value"] == "1"
    assert results["%3FANS ?"]["error"] == "ERR1"  # not scripted in the fake
    assert projector.connections == 1


async def test_survey_stops_when_the_projector_stops_answering(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeProjector(values={"%1POWR": "1"}, reply_delay=0.5)
    await fake.start()
    try:
        argv = ("--host", "127.0.0.1", "--port", str(fake.port), "--timeout", "0.2", "survey")
        assert await _cli(*argv) == 0
    finally:
        await fake.stop()
    output = capsys.readouterr().out
    assert "!! AwolLinkConnectionError" in output
    assert len(fake.received) == 1


async def test_actions_on_the_projector_need_a_host(capsys: pytest.CaptureFixture[str]) -> None:
    assert await _cli("probe") == 2
    assert "--host is required" in capsys.readouterr().err


async def test_wake_sends_to_broadcast_and_host(
    udp: tuple[_Udp, int], capsys: pytest.CaptureFixture[str]
) -> None:
    sink, port = udp
    sink.replies = []
    argv = ("--host", "127.0.0.1", "wake", MAC, "--broadcast", "127.0.0.1", "--wol-port", str(port))
    assert await _cli(*argv) == 0
    for _ in range(100):
        if sink.received:
            break
        await asyncio.sleep(0.01)
    assert sink.received[0] == build_magic_packet(MAC)
    assert f"sent to 127.0.0.1 (port {port})" in capsys.readouterr().out


async def test_discover_lists_answers(
    udp: tuple[_Udp, int], capsys: pytest.CaptureFixture[str]
) -> None:
    sink, port = udp
    assert await _cli("--port", str(port), "discover", "127.0.0.1", "--wait", "0.3") == 0
    assert sink.received == [b"%2SRCH\r"]
    # The unparsable datagram is ignored.
    assert capsys.readouterr().out == "127.0.0.1: '%2ACKN=VisionMaster Pro2 x GoogleTV2891'\n"


async def test_discover_returns_raw_fields(udp: tuple[_Udp, int]) -> None:
    _, port = udp
    found = await discover("127.0.0.1", port=port, wait=0.3)
    assert [(device.host, device.code, device.value) for device in found] == [
        ("127.0.0.1", "ACKN", "VisionMaster Pro2 x GoogleTV2891")
    ]


async def test_discover_without_answer(capsys: pytest.CaptureFixture[str]) -> None:
    assert await _cli("--port", str(_closed_port()), "discover", "127.0.0.1", "--wait", "0.1") == 1
    assert capsys.readouterr().out == "no answer\n"


def test_main_reports_errors(capsys: pytest.CaptureFixture[str]) -> None:
    # Windows retries a refused localhost connection for about 2 s.
    argv = ["--host", "127.0.0.1", "--port", str(_closed_port()), "--timeout", "5", "probe"]
    assert cli.main(argv) == 1
    assert "refused the connection" in capsys.readouterr().err


def test_main_stops_on_ctrl_c(monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupted(args: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_run", interrupted)
    assert cli.main(["probe"]) == 130


@pytest.mark.filterwarnings("ignore:.*found in sys.modules:RuntimeWarning")
@pytest.mark.parametrize(
    "module", ["custom_components.valerion.lib", "custom_components.valerion.lib.cli"]
)
def test_runs_as_a_module(monkeypatch: pytest.MonkeyPatch, module: str) -> None:
    monkeypatch.setattr(sys, "argv", ["awollink", "--help"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module(module, run_name="__main__")
    assert excinfo.value.code == 0
