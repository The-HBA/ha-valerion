"""Tests for the known and learned setting locks."""

from __future__ import annotations

import json

from custom_components.valerion.lib import HdrFormat, LearnedLock, LockTable, protocol

GAMMA = protocol.GAMMA.code
TONE_MAPPING = protocol.DYNAMIC_TONE_MAPPING.code
LASER = protocol.LASER_LEVEL.code


def test_known_locks_apply_in_every_picture_mode() -> None:
    table = LockTable()
    assert table.locked(HdrFormat.SDR, "Theater") == {TONE_MAPPING}
    assert table.locked(HdrFormat.DOLBY_VISION, "Dolby Vision Dark") == {GAMMA, TONE_MAPPING}
    # Gamma in HDR10 was only measured in FILMMAKER MODE, so it is learned.
    assert table.locked(HdrFormat.HDR10, "HDR Theater") == frozenset()
    assert table.locked(None, "Theater") == frozenset()


def test_learned_lock_holds_only_for_its_format_and_mode() -> None:
    table = LockTable()
    assert table.learn(HdrFormat.HDR10, "FILMMAKER MODE", GAMMA)
    assert GAMMA in table.locked(HdrFormat.HDR10, "FILMMAKER MODE")
    assert GAMMA not in table.locked(HdrFormat.HDR10, "HDR Theater")
    assert GAMMA not in table.locked(HdrFormat.SDR, "FILMMAKER MODE")


def test_learning_a_known_or_repeated_lock_changes_nothing() -> None:
    table = LockTable()
    assert not table.learn(HdrFormat.DOLBY_VISION, "Dolby Vision Bright", GAMMA)
    assert table.learn(HdrFormat.HLG, "HDR Standard", LASER)
    assert not table.learn(HdrFormat.HLG, "HDR Standard", LASER)
    assert table.learned == (LearnedLock("hlg", "HDR Standard", LASER),)


def test_lock_without_signal_is_kept_apart() -> None:
    table = LockTable()
    table.learn(None, "Standard", protocol.ASPECT_RATIO.code)
    assert table.locked(None, "Standard") == {protocol.ASPECT_RATIO.code}
    assert table.locked(HdrFormat.SDR, "Standard") == {TONE_MAPPING}


def test_firmware_change_clears_learned_locks() -> None:
    table = LockTable()
    assert table.check_firmware("V02.01.00E.Q0718")  # first firmware seen
    table.learn(HdrFormat.HDR10, "FILMMAKER MODE", GAMMA)
    assert not table.check_firmware("V02.01.00E.Q0718")
    assert not table.check_firmware(None)
    assert table.learned
    assert table.check_firmware("V02.02.00E.Q0901")
    assert table.learned == ()
    assert table.firmware == "V02.02.00E.Q0901"


def test_locks_learned_before_the_firmware_was_known_survive_its_arrival() -> None:
    table = LockTable()
    table.learn(HdrFormat.HDR10, "FILMMAKER MODE", GAMMA)
    assert table.check_firmware("V02.01.00E.Q0718")
    assert table.learned


def test_clear() -> None:
    table = LockTable()
    assert not table.clear()
    table.learn(HdrFormat.HDR10, "FILMMAKER MODE", GAMMA)
    assert table.clear()
    assert table.locked(HdrFormat.HDR10, "FILMMAKER MODE") == frozenset()


def test_round_trip_through_json() -> None:
    table = LockTable("V02.01.00E.Q0718")
    table.learn(HdrFormat.HDR10, "FILMMAKER MODE", GAMMA)
    table.learn(None, "Standard", protocol.ASPECT_RATIO.code)
    stored = json.loads(json.dumps(table.as_dict()))
    assert stored == {
        "firmware": "V02.01.00E.Q0718",
        "learned": [
            {"hdr": "hdr10", "picture_mode": "FILMMAKER MODE", "code": GAMMA},
            {"hdr": "no_signal", "picture_mode": "Standard", "code": protocol.ASPECT_RATIO.code},
        ],
    }
    restored = LockTable.from_dict(stored)
    assert restored.firmware == table.firmware
    assert restored.learned == table.learned


def test_from_dict_tolerates_missing_and_malformed_data() -> None:
    assert LockTable.from_dict(None).learned == ()
    restored = LockTable.from_dict(
        {
            "firmware": 5,
            "learned": [
                {"hdr": "sdr"},
                "junk",
                {"hdr": "sdr", "picture_mode": "Vivid", "code": LASER},
            ],
        }
    )
    assert restored.firmware is None
    assert restored.learned == (LearnedLock("sdr", "Vivid", LASER),)
