"""Command line tool for testing AWOL Link against a real projector.

Run from the repository root::

    python scripts/awollink.py --host 192.168.1.50 probe
    python scripts/awollink.py --host 192.168.1.50 query POWR
    python scripts/awollink.py --host 192.168.1.50 set LASL 5
    python scripts/awollink.py --host 192.168.1.50 raw "%3PICL ?"
    python scripts/awollink.py --host 192.168.1.50 survey -o survey.json
    python scripts/awollink.py --host 192.168.1.50 wake AA:BB:CC:DD:EE:FF
    python scripts/awollink.py discover 192.168.1.50

Every command opens one short session and closes it again, so the Valerion
app and VMote keep working in between.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
import sys
import time
from typing import Any

from . import protocol
from .client import DEFAULT_PORT, DEFAULT_TIMEOUT, AwolLinkClient
from .discovery import discover
from .exceptions import AwolLinkCommandError, AwolLinkError
from .wol import DEFAULT_BROADCAST, DEFAULT_PORT as WOL_PORT, send_magic_packet

_COMMANDS_BY_CODE = {cmd.code: cmd for cmd in protocol.ALL_QUERYABLE}
_COMMANDS_BY_CODE.update(
    {
        cmd.code: cmd
        for cmd in (
            protocol.REMOTE_KEY,
            protocol.VOLUME_STEP,
            protocol.LENS_SHIFT_MENU,
            protocol.ZOOM_MENU,
            protocol.FOCUS_MENU,
        )
    }
)


def _command(code: str, pjlink_class: int | None) -> protocol.Command:
    code = code.upper()
    if pjlink_class is not None:
        return protocol.Command(pjlink_class, code)
    if code in _COMMANDS_BY_CODE:
        return _COMMANDS_BY_CODE[code]
    msg = f"unknown command code {code!r}; pass --class to force one"
    raise SystemExit(msg)


async def _probe(client: AwolLinkClient) -> int:
    started = time.monotonic()
    greeting = await client.probe()
    print(f"greeting: {greeting!r} ({time.monotonic() - started:.2f}s)")
    return 0


async def _query(client: AwolLinkClient, command: protocol.Command) -> int:
    async with client.session() as session:
        value = await session.query(command)
    print(f"{command.header}={value!r}  ({session.last_round_trip or 0:.2f}s)")
    return 0


async def _set(client: AwolLinkClient, command: protocol.Command, value: str) -> int:
    async with client.session() as session:
        await session.send(command, value)
        readback = await session.query(command)
    print(f"{command.header} {value} -> OK, now {readback!r}")
    return 0


async def _raw(client: AwolLinkClient, line: str) -> int:
    async with client.session() as session:
        response = await session.raw(line)
    print(f"{response.raw!r}  ({session.last_round_trip or 0:.2f}s)")
    return 0


async def _survey(client: AwolLinkClient, out: str | None) -> int:
    """Run every documented query in one session and record raw replies."""
    results: list[dict[str, Any]] = []
    async with client.session() as session:
        greeting = client.last_greeting
        for command in protocol.ALL_QUERYABLE:
            entry: dict[str, Any] = {"command": command.query()}
            started = time.monotonic()
            try:
                response = await session.raw(command.query(), expect=command)
                entry["raw"] = response.raw
                entry["value"] = response.value
            except AwolLinkCommandError as err:
                entry["error"] = err.error
            except AwolLinkError as err:
                entry["error"] = f"{type(err).__name__}: {err}"
                entry["seconds"] = round(time.monotonic() - started, 3)
                results.append(entry)
                print(f"{command.query():<10} !! {entry['error']}")
                break
            entry["seconds"] = round(time.monotonic() - started, 3)
            results.append(entry)
            shown = entry.get("raw", entry.get("error"))
            print(f"{command.query():<10} {entry['seconds']:>5.2f}s  {shown!r}")
    document = {
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "host": client.host,
        "port": client.port,
        "greeting": greeting,
        "results": results,
    }
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, ensure_ascii=False)
        print(f"written {out}")
    return 0


async def _wake(mac: str, targets: list[str], port: int) -> int:
    sent = await send_magic_packet(mac, targets=targets, port=port)
    print(f"magic packet for {mac} sent to {', '.join(sent)} (port {port})")
    return 0


async def _discover(target: str, port: int, wait: float) -> int:
    found = await discover(target, port=port, wait=wait)
    if not found:
        print("no answer")
        return 1
    for device in found:
        print(f"{device.host}: {device.raw!r}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(prog="awollink", description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", help="projector IP address or hostname")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--code", help="AWOL Link security code, if one is set")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("probe", help="connect, read the greeting, disconnect")

    p_query = sub.add_parser("query", help="query one command, e.g. POWR")
    p_query.add_argument("code")
    p_query.add_argument("--class", dest="pjlink_class", type=int)

    p_set = sub.add_parser("set", help="set one command, e.g. LASL 5")
    p_set.add_argument("code")
    p_set.add_argument("value")
    p_set.add_argument("--class", dest="pjlink_class", type=int)

    p_raw = sub.add_parser("raw", help='send a raw line, e.g. "%%3PICL ?"')
    p_raw.add_argument("line")

    p_survey = sub.add_parser("survey", help="run every documented query and record replies")
    p_survey.add_argument("-o", "--out", help="write results to this JSON file")

    p_wake = sub.add_parser("wake", help="send a Wake-on-LAN magic packet")
    p_wake.add_argument("mac")
    p_wake.add_argument("--broadcast", default=DEFAULT_BROADCAST)
    # --host (if given) also gets a unicast copy, which crosses routers/VLANs.
    p_wake.add_argument("--wol-port", type=int, default=WOL_PORT)

    p_disc = sub.add_parser("discover", help="send %%2SRCH over UDP and list answers")
    p_disc.add_argument("target", nargs="?", default="255.255.255.255")
    p_disc.add_argument("--wait", type=float, default=2.0)
    return parser


async def _run(args: argparse.Namespace) -> int:
    if args.action == "wake":
        targets = [args.broadcast, *([args.host] if args.host else [])]
        return await _wake(args.mac, targets, args.wol_port)
    if args.action == "discover":
        return await _discover(args.target, args.port, args.wait)
    if not args.host:
        print("--host is required for this action", file=sys.stderr)
        return 2
    client = AwolLinkClient(args.host, args.port, security_code=args.code, timeout=args.timeout)
    if args.action == "probe":
        return await _probe(client)
    if args.action == "query":
        return await _query(client, _command(args.code, args.pjlink_class))
    if args.action == "set":
        return await _set(client, _command(args.code, args.pjlink_class), args.value)
    if args.action == "raw":
        return await _raw(client, args.line)
    if args.action == "survey":
        return await _survey(client, args.out)
    return 2


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except AwolLinkError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
