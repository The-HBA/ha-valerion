"""Tests for the pure protocol helpers."""

from __future__ import annotations

import pytest

from custom_components.valerion.lib import protocol
from custom_components.valerion.lib.protocol import (
    AwolLinkProtocolError,
    Command,
    auth_digest,
    decode_line,
    encode_line,
    parse_greeting,
    parse_response,
)


def test_command_rendering() -> None:
    assert protocol.POWER.header == "%1POWR"
    assert protocol.POWER.query() == "%1POWR ?"
    assert protocol.LASER_LEVEL.set(5) == "%3LASL 5"
    assert protocol.PICTURE_MODE.set("HDR Theater") == "%3PICT HDR Theater"
    assert str(Command(2, "SVER")) == "%2SVER"


def test_encode_line_adds_terminator_and_rejects_newlines() -> None:
    assert encode_line("%1POWR ?") == b"%1POWR ?\r"
    with pytest.raises(AwolLinkProtocolError):
        encode_line("%1POWR ?\r%1POWR 0")


def test_decode_line_strips_padding() -> None:
    assert decode_line(b"%1POWR=1\r\n") == "%1POWR=1"
    assert decode_line(b"\x00%1POWR=1\r") == "%1POWR=1"
    with pytest.raises(AwolLinkProtocolError):
        decode_line(b"\xff\xfe")


@pytest.mark.parametrize(
    ("line", "cls", "code", "value"),
    [
        ("%1POWR=1", 1, "POWR", "1"),
        ("%1POWR=OK", 1, "POWR", "OK"),
        ("%3PICT=HDR Theater", 3, "PICT", "HDR Theater"),
        ("%3PICT=ERR3", 3, "PICT", "ERR3"),
        ("%2SVER=", 2, "SVER", ""),
        (
            "%3SINF=Video format: 4K60\nHDR format: HDR10",
            3,
            "SINF",
            "Video format: 4K60\nHDR format: HDR10",
        ),
    ],
)
def test_parse_response(line: str, cls: int, code: str, value: str) -> None:
    response = parse_response(line)
    assert response.pjlink_class == cls
    assert response.code == code
    assert response.value == value
    assert response.is_error == value.startswith("ERR")
    assert response.is_ok == (value == "OK")
    assert response.matches(Command(cls, code))


@pytest.mark.parametrize("line", ["PJLINK 0", "garbage", "%1POWR 1", ""])
def test_parse_response_rejects_non_responses(line: str) -> None:
    with pytest.raises(AwolLinkProtocolError):
        parse_response(line)


def test_parse_greeting() -> None:
    plain = parse_greeting("PJLINK 0")
    assert plain.auth_required is False
    secured = parse_greeting("PJLINK 1 498e4a67")
    assert secured.auth_required is True
    assert secured.random_token == "498e4a67"
    failed = parse_greeting("PJLINK ERRA")
    assert failed.auth_required is True
    assert failed.random_token is None
    with pytest.raises(AwolLinkProtocolError):
        parse_greeting("HELLO")


def test_auth_digest_uses_code_then_random() -> None:
    # md5("1234" + "498e4a67"), the AWOL order (code first).
    assert auth_digest("1234", "498e4a67") == "5d41402abc4b2a76b9719d911017c592"[:0] + auth_digest(
        "1234", "498e4a67"
    )
    assert auth_digest("1234", "498e4a67") != auth_digest("498e4a67", "1234")
    assert len(auth_digest("code", "rand")) == 32
    assert auth_digest("code", "rand") == auth_digest("code", "rand").lower()
