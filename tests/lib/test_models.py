"""Tests for value tables and reply parsers."""

from __future__ import annotations

import pytest

from custom_components.valerion.lib import (
    ALL_PICTURE_MODES,
    Gamma,
    MotionEnhancement,
    PowerState,
    SignalInfo,
    split_multi_value,
    split_picture_mode_list,
)


def test_power_codes_follow_awol_not_pjlink() -> None:
    assert PowerState("0") is PowerState.STANDBY
    assert PowerState("1") is PowerState.ON
    assert PowerState("2") is PowerState.OFF


def test_motion_enhancement_uses_response_sheet() -> None:
    assert MotionEnhancement("3") is MotionEnhancement.CLEAR
    assert MotionEnhancement("4") is MotionEnhancement.STANDARD


def test_gamma_hdr_values_exist() -> None:
    assert Gamma("4") is Gamma.SMPTE2084
    assert Gamma("5") is Gamma.HLG


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Fan1: 1200\nFan2: 1150", ["Fan1: 1200", "Fan2: 1150"]),
        ("1200 1150", ["1200", "1150"]),
        ("1200,1150", ["1200", "1150"]),
        ("", []),
    ],
)
def test_split_multi_value(raw: str, expected: list[str]) -> None:
    assert split_multi_value(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("HDR Standard,HDR Vivid,HDR Theater", ["HDR Standard", "HDR Vivid", "HDR Theater"]),
        ("Standard\nVivid\nPC/Game", ["Standard", "Vivid", "PC/Game"]),
        ("HDR Theater", ["HDR Theater"]),
        ("Standard Vivid Sports Theater", ["Standard", "Vivid", "Sports", "Theater"]),
        ("", []),
    ],
)
def test_split_picture_mode_list(raw: str, expected: list[str]) -> None:
    assert split_picture_mode_list(raw) == expected


def test_all_documented_picture_modes_are_unique() -> None:
    assert len(set(ALL_PICTURE_MODES)) == len(ALL_PICTURE_MODES) == 22


def test_signal_info_parses_labelled_lines() -> None:
    raw = (
        "Video format: 3840x2160p60\nAudio format: Dolby Atmos\nColor depth: 10bit\n"
        "Color format: YCbCr 4:2:2\nHDR format: HDR10\nColor space: BT.2020"
    )
    info = SignalInfo.parse(raw)
    assert info.video_format == "3840x2160p60"
    assert info.audio_format == "Dolby Atmos"
    assert info.color_depth == "10bit"
    assert info.color_format == "YCbCr 4:2:2"
    assert info.hdr_format == "HDR10"
    assert info.color_space == "BT.2020"
    assert info.raw == raw


def test_signal_info_handles_no_information_and_partial() -> None:
    assert SignalInfo.parse("255").video_format is None
    partial = SignalInfo.parse("1080p60,PCM")
    assert partial.video_format == "1080p60"
    assert partial.audio_format == "PCM"
    assert partial.hdr_format is None
