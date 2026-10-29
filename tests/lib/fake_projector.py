"""A scripted fake AWOL Link projector for tests.

It speaks just enough of the protocol to exercise the client: greeting with
or without a security code, scripted replies per command header, ERRx
answers, the "silent" standby behaviour and the single-session rule.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib


@dataclass
class FakeProjector:
    """Scripted projector listening on 127.0.0.1."""

    security_code: str | None = None
    random_token: str = "498e4a67"
    #: Reply value per command header, e.g. {"%1POWR": "1"}.
    values: dict[str, str] = field(default_factory=dict)
    #: Headers that answer ERR3 on query or set.
    unavailable: set[str] = field(default_factory=set)
    #: If True the projector accepts connections but never greets (standby).
    silent: bool = False
    #: Delay before every reply, to simulate the real half-second latency.
    reply_delay: float = 0.0
    #: Reply lines injected before the next real answer (unsolicited).
    unsolicited: list[str] = field(default_factory=list)
    received: list[str] = field(default_factory=list)
    connections: int = 0
    greeted: int = 0
    _server: asyncio.Server | None = None
    _busy: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def start(self) -> None:
        """Start listening on an ephemeral port."""
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)

    @property
    def port(self) -> int:
        """Return the listening port."""
        assert self._server is not None
        return int(self._server.sockets[0].getsockname()[1])

    async def stop(self) -> None:
        """Stop the server."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        try:
            if self.silent:
                # Real projectors keep the socket open and never answer.
                await reader.read()
                return
            async with self._busy:  # one session at a time, like the hardware
                if not await self._greet(reader, writer):
                    return
                await self._serve(reader, writer)
        except ConnectionError, asyncio.IncompleteReadError:
            pass
        finally:
            writer.close()

    async def _greet(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bool:
        if self.security_code is None:
            # A VisionMaster Pro2 sends a trailing space (observed 2026-10-29).
            writer.write(b"PJLINK 0 \r")
            await writer.drain()
            self.greeted += 1
            return True
        writer.write(f"PJLINK 1 {self.random_token}\r".encode())
        await writer.drain()
        digest_line = (await reader.readuntil(b"\r")).decode().strip()
        expected = hashlib.md5(  # noqa: S324
            f"{self.security_code}{self.random_token}".encode()
        ).hexdigest()
        if digest_line != expected:
            writer.write(b"PJLINK ERRA\r")
            await writer.drain()
            return False
        writer.write(b"PJLINK 1 OK\r")
        await writer.drain()
        self.greeted += 1
        return True

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        while True:
            line = (await reader.readuntil(b"\r")).decode().strip("\r\n")
            self.received.append(line)
            header, _, argument = line.partition(" ")
            if self.reply_delay:
                await asyncio.sleep(self.reply_delay)
            while self.unsolicited:
                writer.write(f"{self.unsolicited.pop(0)}\r".encode())
            writer.write(f"{self._reply(header, argument)}\r".encode())
            await writer.drain()

    def _reply(self, header: str, argument: str) -> str:
        if header in self.unavailable:
            return f"{header}=ERR3"
        if argument == "?":
            if header.endswith(("LSMN", "ZMMN", "FCMN")):
                return f"{header}=OK"  # lens menus: actions written as queries
            if header in self.values:
                return f"{header}={self.values[header]}"
            return f"{header}=ERR1"
        if header in self.values or header.endswith(("RCNC", "SVOL")):
            if header in self.values:
                self.values[header] = argument
            return f"{header}=OK"
        return f"{header}=ERR1"
