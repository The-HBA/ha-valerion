"""Tests for value tables and reply parsers."""

from __future__ import annotations

import pytest

from custom_components.valerion.lib import (
    ALL_PICTURE_MODES,
    AudioFormat,
    ColorDepth,
    ColorFormat,
    ColorPrimaries,
    DeviceIdentity,
    Gamma,
    HdrFormat,
    MotionEnhancement,
    PowerState,
    SignalInfo,
    VideoTiming,
    parse_number_list,
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
        # A name the official list does not know is kept as it is.
        ("Calibrated 2", ["Calibrated 2"]),
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
    assert info.color_primaries == "BT.2020"
    assert info.raw == raw


def test_replies_observed_on_visionmaster_pro2() -> None:
    """Replies recorded from a VisionMaster Pro2, firmware V02.01.00E.Q0718, on the home screen."""
    assert split_multi_value("1770 1710 0 0 0 0 0") == ["1770", "1710", "0", "0", "0", "0", "0"]
    assert len(split_multi_value("33 48 0 0 0 0 0 0")) == 8
    assert split_multi_value("30 31 32 33") == ["30", "31", "32", "33"]
    assert split_picture_mode_list(
        "Vivid,Standard,Sports,Energy Saving,Theater,FILMMAKER MODE"
    ) == [
        "Vivid",
        "Standard",
        "Sports",
        "Energy Saving",
        "Theater",
        "FILMMAKER MODE",
    ]
    info = SignalInfo.parse("0*0p@0Hz 0 255 3 0 0")
    assert info.video_format == "0*0p@0Hz"
    assert info.audio_format == "0"
    assert info.color_depth == "255"
    assert info.color_format == "3"
    assert info.hdr_format == "0"
    assert info.color_primaries == "0"
    assert not info.has_signal
    assert info.hdr is None  # codes without a signal describe nothing


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("V02.01.00E.Q0718 83 OEM01.0.0.0", "V02.01.00E.Q0718"),  # Pro2, on
        ("V02.01.00E.Q0718 00 OEM01.0.0.0", "V02.01.00E.Q0718"),  # Pro2, light standby
        ("V1.0", "V1.0"),
        ("", None),
        (None, None),
    ],
)
def test_firmware_is_first_sver_field(raw: str | None, expected: str | None) -> None:
    assert DeviceIdentity(software_version=raw).firmware == expected


def test_signal_info_handles_no_information_and_partial() -> None:
    assert SignalInfo.parse("255").video_format is None
    partial = SignalInfo.parse("1080p60,PCM")
    assert partial.video_format == "1080p60"
    assert partial.audio_format == "PCM"
    assert partial.hdr_format is None


@pytest.mark.parametrize(
    ("raw", "timing", "decoded"),
    [
        # Replies recorded on the Pro2 with HDMI signals (docs/protocol.md, 2026-10-30).
        (
            "1920*1080p@24Hz 0 3 1 0 0",
            "1920\u00d71080p 24 Hz",
            (
                AudioFormat.PCM,
                ColorDepth.BIT_12,
                ColorFormat.YUV_422,
                HdrFormat.SDR,
                ColorPrimaries.BT709,
            ),
        ),
        (
            "3840*2160p@24Hz 0 3 1 1 2",
            "3840\u00d72160p 24 Hz",
            (
                AudioFormat.PCM,
                ColorDepth.BIT_12,
                ColorFormat.YUV_422,
                HdrFormat.HDR10,
                ColorPrimaries.BT2020,
            ),
        ),
        (
            "3840*2160p@60Hz 0 1 3 4 2",
            "3840\u00d72160p 60 Hz",
            (
                AudioFormat.PCM,
                ColorDepth.BIT_8,
                ColorFormat.RGB,
                HdrFormat.DOLBY_VISION,
                ColorPrimaries.BT2020,
            ),
        ),
        # Example from AWOL support (via Michael Konieczki).
        (
            "3840*2160p@24Hz 3 2 0 4 0",
            "3840\u00d72160p 24 Hz",
            (
                AudioFormat.DOLBY_AUDIO,
                ColorDepth.BIT_10,
                ColorFormat.YUV_420,
                HdrFormat.DOLBY_VISION,
                ColorPrimaries.BT709,
            ),
        ),
    ],
)
def test_signal_info_decodes_codes(
    raw: str,
    timing: str,
    decoded: tuple[AudioFormat, ColorDepth, ColorFormat, HdrFormat, ColorPrimaries],
) -> None:
    info = SignalInfo.parse(raw)
    assert info.has_signal
    assert str(info.timing) == timing
    assert (info.audio, info.depth, info.chroma, info.hdr, info.primaries) == decoded


def test_signal_info_unavailable_and_unknown_codes() -> None:
    no_signal = SignalInfo.parse("255")
    assert not no_signal.has_signal
    assert no_signal.timing is None
    assert no_signal.audio is None
    odd = SignalInfo.parse("1920*1080p@50Hz 99 255 3 7 1")
    assert odd.has_signal
    assert odd.audio is None  # unknown code
    assert odd.depth is None  # 255 = unavailable
    assert odd.chroma is ColorFormat.RGB
    assert odd.hdr is None
    assert odd.primaries is ColorPrimaries.DCI_P3


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("3840*2160p@23.976Hz", VideoTiming(3840, 2160, interlaced=False, refresh_rate=23.976)),
        ("1920x1080i@50Hz", VideoTiming(1920, 1080, interlaced=True, refresh_rate=50.0)),
        ("0*0p@0Hz", VideoTiming(0, 0, interlaced=False, refresh_rate=0.0)),
        ("garbage", None),
    ],
)
def test_video_timing_parse(raw: str, expected: VideoTiming | None) -> None:
    assert VideoTiming.parse(raw) == expected


def test_video_timing_text() -> None:
    assert str(VideoTiming(1920, 1080, interlaced=True, refresh_rate=59.94)) == (
        "1920\u00d71080i 59.94 Hz"
    )


@pytest.mark.parametrize(
    ("raw", "text"),
    [
        # Measured on the Pro2 with an MVC film (2026-10-31).
        ("1920*2205p@24Hz", "1920\u00d71080p 24 Hz 3D"),
        ("1280*1470p@60Hz", "1280\u00d7720p 60 Hz 3D"),
        ("1920*2228i@60Hz", "1920\u00d71080i 60 Hz 3D"),
    ],
)
def test_frame_packed_3d(raw: str, text: str) -> None:
    timing = VideoTiming.parse(raw)
    assert timing is not None
    assert timing.is_3d
    assert str(timing) == text


def test_signal_info_3d() -> None:
    three_d = SignalInfo.parse("1920*2205p@24Hz 0 3 1 0 0")
    assert three_d.is_3d
    assert three_d.hdr is HdrFormat.SDR  # nothing else marks 3D
    assert not SignalInfo.parse("1920*1080p@24Hz 0 3 1 0 0").is_3d
    assert not SignalInfo.parse("255").is_3d


def test_parse_number_list() -> None:
    assert parse_number_list("1770 1710 0 0 0 0 0") == (1770, 1710, 0, 0, 0, 0, 0)
    assert parse_number_list("33 48 x") == (33, 48, None)
    assert parse_number_list("") == ()
