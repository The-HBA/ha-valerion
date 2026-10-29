"""Asyncio TCP client for AWOL Link.

Design rules, learned from the VMote author and confirmed by the Unfolded
Circle driver:

* The projector serves ONE control session at a time. A second connection is
  accepted but never greeted until the first one closes. Holding a session
  open locks out the Valerion app and VMote, so this client opens a session,
  does its work and closes it again. Several commands may be sent inside one
  session; that is much faster than one connection per command.
* In standby the projector accepts the TCP connection but never answers.
  The client reports that as :class:`AwolLinkUnresponsiveError`.
* With a security code the greeting is ``PJLINK 1 <random>``; the client
  answers with ``md5(code + random)`` on its own line and waits for
  ``PJLINK 1 OK``.
* Replies take roughly half a second. All sessions of one client are
  serialised through an ``asyncio.Lock``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager, suppress
import logging
import time
from typing import TYPE_CHECKING, Final, Self

from .exceptions import (
    AwolLinkAuthError,
    AwolLinkCommandError,
    AwolLinkConnectionError,
    AwolLinkUnresponsiveError,
)
from .protocol import (
    GREETING_AUTH_FAILED,
    GREETING_AUTH_OK,
    GREETING_PREFIX,
    AwolLinkProtocolError,
    Command,
    Response,
    auth_digest,
    decode_line,
    encode_line,
    parse_greeting,
    parse_response,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT: Final = 4352
DEFAULT_TIMEOUT: Final = 3.0
#: Pause between the digest and the first command; some firmware needs a beat.
_POST_AUTH_DELAY: Final = 0.05
#: Maximum unsolicited lines skipped while waiting for the matching reply.
_MAX_SKIPPED_LINES: Final = 10

UnsolicitedCallback = Callable[[Response], None]


class AwolLinkSession:
    """One open control session. Create it with :meth:`AwolLinkClient.session`."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        timeout: float,
        on_unsolicited: UnsolicitedCallback | None,
    ) -> None:
        """Wrap an authenticated stream pair."""
        self._reader = reader
        self._writer = writer
        self._timeout = timeout
        self._on_unsolicited = on_unsolicited
        self.last_round_trip: float | None = None

    async def raw(self, line: str, *, expect: Command | None = None) -> Response:
        """Send ``line`` verbatim and return the matching response.

        ``expect`` names the command whose reply we wait for; by default it is
        derived from the first token of ``line``. ERRx replies raise
        :class:`AwolLinkCommandError`.
        """
        header = line.split(" ", 1)[0]
        expected_code = expect.code if expect is not None else header[2:6]
        self._writer.write(encode_line(line))
        started = time.monotonic()
        try:
            async with asyncio.timeout(self._timeout):
                await self._writer.drain()
                for _ in range(_MAX_SKIPPED_LINES):
                    data = await self._reader.readuntil(b"\r")
                    text = decode_line(data)
                    if not text:
                        continue
                    if text.startswith(GREETING_AUTH_FAILED):
                        raise AwolLinkAuthError(text)
                    try:
                        response = parse_response(text)
                    except AwolLinkProtocolError:
                        _LOGGER.debug("Ignoring unparsable line %r", text)
                        continue
                    if response.code == expected_code:
                        self.last_round_trip = time.monotonic() - started
                        if response.is_error:
                            raise AwolLinkCommandError(line, response.value)
                        return response
                    _LOGGER.debug("Unsolicited line while waiting for %s: %r", header, text)
                    if self._on_unsolicited is not None:
                        self._on_unsolicited(response)
        except TimeoutError as err:
            msg = f"no reply to {line!r} within {self._timeout}s"
            raise AwolLinkConnectionError(msg) from err
        except (asyncio.IncompleteReadError, ConnectionError, OSError) as err:
            msg = f"connection lost while waiting for reply to {line!r}: {err}"
            raise AwolLinkConnectionError(msg) from err
        msg = f"no reply to {line!r} after {_MAX_SKIPPED_LINES} unrelated lines"
        raise AwolLinkConnectionError(msg)

    async def query(self, command: Command) -> str:
        """Send ``<command> ?`` and return the reply value."""
        response = await self.raw(command.query(), expect=command)
        return response.value

    async def send(self, command: Command, value: str | int) -> None:
        """Send ``<command> <value>`` and expect ``OK``."""
        response = await self.raw(command.set(value), expect=command)
        if not response.is_ok:
            _LOGGER.debug("%s replied %r instead of OK", command, response.value)

    async def query_many(
        self, commands: list[Command] | tuple[Command, ...]
    ) -> dict[str, str | AwolLinkCommandError]:
        """Query several commands; failures are returned, not raised.

        Connection problems still raise, because nothing after them can
        succeed. The result is keyed by command code (``"POWR"``).
        """
        result: dict[str, str | AwolLinkCommandError] = {}
        for command in commands:
            try:
                result[command.code] = await self.query(command)
            except AwolLinkCommandError as err:
                result[command.code] = err
        return result


class AwolLinkClient:
    """Serialised, short-session client for one projector."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        *,
        security_code: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        on_unsolicited: UnsolicitedCallback | None = None,
    ) -> None:
        """Create a client; nothing is connected until a session is opened."""
        self.host = host
        self.port = port
        self.security_code = security_code or None
        self.timeout = timeout
        self.on_unsolicited = on_unsolicited
        self._lock = asyncio.Lock()
        self.last_greeting: str | None = None

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AwolLinkSession]:
        """Open a control session, yield it, and always close it afterwards."""
        async with self._lock:
            reader, writer = await self._open()
            try:
                yield AwolLinkSession(
                    reader,
                    writer,
                    timeout=self.timeout,
                    on_unsolicited=self.on_unsolicited,
                )
            finally:
                await _close(writer)

    async def query(self, command: Command) -> str:
        """Open a session for a single query."""
        async with self.session() as session:
            return await session.query(command)

    async def send(self, command: Command, value: str | int) -> None:
        """Open a session for a single set command."""
        async with self.session() as session:
            await session.send(command, value)

    async def probe(self) -> str:
        """Open and close a session; return the greeting line.

        Raises :class:`AwolLinkUnresponsiveError` when the projector is in
        standby or busy, :class:`AwolLinkConnectionError` when unreachable
        and :class:`AwolLinkAuthError` when the security code is wrong.
        """
        async with self.session():
            return self.last_greeting or ""

    async def _open(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        writer: asyncio.StreamWriter | None = None
        try:
            async with asyncio.timeout(self.timeout):
                reader, writer = await asyncio.open_connection(self.host, self.port)
        except TimeoutError as err:
            msg = f"timeout connecting to {self.host}:{self.port}"
            raise AwolLinkConnectionError(msg) from err
        except OSError as err:
            msg = f"cannot connect to {self.host}:{self.port}: {err}"
            raise AwolLinkConnectionError(msg) from err

        try:
            try:
                async with asyncio.timeout(self.timeout):
                    data = await reader.readuntil(b"\r")
            except TimeoutError as err:
                msg = (
                    f"{self.host}:{self.port} accepted the connection but sent no "
                    "greeting (projector in standby or another controller connected)"
                )
                raise AwolLinkUnresponsiveError(msg) from err
            except (asyncio.IncompleteReadError, ConnectionError, OSError) as err:
                msg = f"connection to {self.host}:{self.port} closed before greeting"
                raise AwolLinkConnectionError(msg) from err

            text = decode_line(data)
            self.last_greeting = text
            if not text.startswith(GREETING_PREFIX):
                msg = f"unexpected greeting from {self.host}: {text!r}"
                raise AwolLinkProtocolError(msg)  # noqa: TRY301
            greeting = parse_greeting(text)
            if greeting.auth_required:
                await self._authenticate(reader, writer, greeting.random_token)
        except BaseException:
            await _close(writer)
            raise
        return reader, writer

    async def _authenticate(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        random_token: str | None,
    ) -> None:
        if random_token is None:
            msg = "projector requires a security code (PJLINK ERRA)"
            raise AwolLinkAuthError(msg)
        if not self.security_code:
            msg = "projector requires a security code but none is configured"
            raise AwolLinkAuthError(msg)
        digest = auth_digest(self.security_code, random_token)
        writer.write(encode_line(digest))
        try:
            async with asyncio.timeout(self.timeout):
                await writer.drain()
                data = await reader.readuntil(b"\r")
        except TimeoutError as err:
            msg = "no answer to the authentication digest"
            raise AwolLinkAuthError(msg) from err
        except (asyncio.IncompleteReadError, ConnectionError, OSError) as err:
            msg = f"connection closed during authentication: {err}"
            raise AwolLinkConnectionError(msg) from err
        text = decode_line(data)
        if text.startswith(GREETING_AUTH_FAILED) or not text.startswith(GREETING_AUTH_OK):
            msg = f"security code rejected: {text!r}"
            raise AwolLinkAuthError(msg)
        await asyncio.sleep(_POST_AUTH_DELAY)

    def __repr__(self) -> str:
        """Return a debugging representation without the security code."""
        return f"AwolLinkClient(host={self.host!r}, port={self.port})"

    async def __aenter__(self) -> Self:
        """Allow ``async with AwolLinkClient(...) as client`` for symmetry."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Nothing is held open between sessions."""


async def _close(writer: asyncio.StreamWriter) -> None:
    writer.close()
    with suppress(ConnectionError, OSError, TimeoutError, asyncio.CancelledError):
        async with asyncio.timeout(1.0):
            await writer.wait_closed()
