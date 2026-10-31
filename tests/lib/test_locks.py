"""Tests for the known and learned setting locks."""

from __future__ import annotations

import json

from custom_components.valerion.lib import HdrFormat, LearnedLock, LockTable, protocol

GAMMA = protocol.GAMMA.code
TONE_MAPPING = protocol.DYNAMIC_TONE_MAPPING.code
LASER = protocol.LASER_LEVEL.code
LENS_SHIFT = protocol.LENS_SHIFT_MENU.code


def test_known_locks_apply_in_every_picture_mode() -> None:
    table = LockTable()
    assert table.locked(HdrFormat.SDR, "Theater") == {TONE_MAPPING}
    assert table.locked(HdrFormat.DOLBY_VISION, "Dolby Vision Dark") == {GAMMA, TONE_MAPPING}
    assert table.locked(HdrFormat.HDR10, "HDR Theater") == {GAMMA}
    assert table.locked(HdrFormat.HDR10_PLUS, "HDR10+ Game") == {GAMMA, TONE_MAPPING}
    # HLG is not measured yet, so its locks are learned.
    assert table.locked(HdrFormat.HLG, "HDR Theater") == frozenset()
    assert table.locked(None, "Theater") == frozenset()


def test_learned_lock_holds_only_for_its_format_and_mode() -> None:
    table = LockTable()
    assert table.learn(HdrFormat.HLG, "FILMMAKER MODE", GAMMA)
    assert GAMMA in table.locked(HdrFormat.HLG, "FILMMAKER MODE")
    assert GAMMA not in table.locked(HdrFormat.HLG, "HDR Theater")
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
    table.learn(HdrFormat.HLG, "FILMMAKER MODE", GAMMA)
    assert not table.check_firmware("V02.01.00E.Q0718")
    assert not table.check_firmware(None)
    assert table.learned
    assert table.check_firmware("V02.02.00E.Q0901")
    assert table.learned == ()
    assert table.firmware == "V02.02.00E.Q0901"


def test_locks_learned_before_the_firmware_was_known_survive_its_arrival() -> None:
    table = LockTable()
    table.learn(HdrFormat.HLG, "FILMMAKER MODE", GAMMA)
    assert table.check_firmware("V02.01.00E.Q0718")
    assert table.learned


def test_clear() -> None:
    table = LockTable()
    assert not table.clear()
    table.learn(HdrFormat.HLG, "FILMMAKER MODE", GAMMA)
    assert table.clear()
    assert table.locked(HdrFormat.HLG, "FILMMAKER MODE") == frozenset()


def test_round_trip_through_json() -> None:
    table = LockTable("V02.01.00E.Q0718")
    table.learn(HdrFormat.HLG, "FILMMAKER MODE", GAMMA)
    table.learn(None, "Standard", protocol.ASPECT_RATIO.code)
    table.mark_unsupported(LENS_SHIFT)
    stored = json.loads(json.dumps(table.as_dict()))
    assert stored == {
        "firmware": "V02.01.00E.Q0718",
        "learned": [
            {"hdr": "hlg", "picture_mode": "FILMMAKER MODE", "code": GAMMA},
            {"hdr": "no_signal", "picture_mode": "Standard", "code": protocol.ASPECT_RATIO.code},
        ],
        "unsupported": [LENS_SHIFT],
    }
    restored = LockTable.from_dict(stored)
    assert restored.firmware == table.firmware
    assert restored.learned == table.learned
    assert restored.unsupported == {LENS_SHIFT}


def test_unsupported_commands_are_remembered_until_cleared() -> None:
    table = LockTable()
    assert table.mark_unsupported(LENS_SHIFT)
    assert not table.mark_unsupported(LENS_SHIFT)
    assert table.unsupported == {LENS_SHIFT}
    assert table.clear()
    assert table.unsupported == frozenset()
    assert not table.clear()


def test_firmware_change_clears_unsupported_commands() -> None:
    table = LockTable("V02.01.00E.Q0718", unsupported=(LENS_SHIFT,))
    assert table.check_firmware("V02.02.00E.Q0901")
    assert table.unsupported == frozenset()


def test_stored_tables_without_unsupported_still_load() -> None:
    assert LockTable.from_dict({"firmware": "V1", "learned": []}).unsupported == frozenset()
    assert LockTable.from_dict({"unsupported": "LSMN"}).unsupported == frozenset()


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
