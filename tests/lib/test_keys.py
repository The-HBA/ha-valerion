"""Tests for the named key presses."""

from __future__ import annotations

import pytest

from custom_components.valerion.lib import KEYS, AwolLinkClient, key_press, protocol

from .fake_projector import FakeProjector

# Every key line, straight from the official AWOL Link command list.
DOCUMENTED_LINES = {
    "up": "%3RCNC 0",
    "down": "%3RCNC 1",
    "left": "%3RCNC 2",
    "right": "%3RCNC 3",
    "ok": "%3RCNC 4",
    "return": "%3RCNC 5",
    "menu": "%3RCNC 6",
    "settings": "%3RCNC 7",
    "home": "%3RCNC 8",
    "volume_down": "%2SVOL 0",
    "volume_up": "%2SVOL 1",
    "lens_shift": "%3LSMN ?",
    "zoom": "%3ZMMN ?",
    "focus": "%3FCMN ?",
}


def test_every_key_is_a_documented_line() -> None:
    assert {name: press.line for name, press in KEYS.items()} == DOCUMENTED_LINES


def test_key_names_are_lowercase_identifiers() -> None:
    for name in KEYS:
        assert name == name.lower()
        assert name.isidentifier()


@pytest.mark.parametrize("name", ["OK", " Home ", "Volume_Up"])
def test_key_press_ignores_case_and_spaces(name: str) -> None:
    assert key_press(name) is KEYS[name.strip().lower()]


def test_key_press_rejects_unknown_names() -> None:
    with pytest.raises(KeyError):
        key_press("power")


async def test_key_sequence_in_one_session(projector: FakeProjector) -> None:
    client = AwolLinkClient("127.0.0.1", projector.port)
    presses = [key_press(name) for name in ("down", "down", "ok", "zoom", "volume_up")]
    async with client.session() as session:
        for press in presses:
            await session.send(press.command, press.value)
    assert projector.connections == 1
    assert projector.received == [press.line for press in presses]
    assert presses[0].command is protocol.REMOTE_KEY
