# AWOL Link protocol notes

This file collects what the official command list says and what real
projectors actually do. The official list is the
[AWOL Link article](https://support.valerion.com/hc/en-us/articles/17088458288143-What-is-AWOL-Link)
and its linked spreadsheet. Observations marked **observed** were measured on
real hardware with the model and firmware noted; everything else is still
to be confirmed.

## Transport

- TCP port 4352, one line per message, terminated by `\r` (carriage return).
- Greeting on connect: `PJLINK 0` (no security code) or `PJLINK 1 <random>`.
- Security code: reply with `md5(code + random)` as 32 lowercase hex digits on
  its own line, then expect `PJLINK 1 OK`. (Standard PJLink would hash
  `random + password` and prefix the digest to the first command; AWOL Link
  does not accept that.)
- One control session at a time. A second TCP connection is accepted but
  never greeted until the first one closes.
- Standby comes in (at least) two depths. In *light standby* the projector
  still greets and answers queries with `%1POWR=0`. In *deep standby*,
  reported by the VMote author, it accepts TCP connections but never sends
  the greeting, and power-on needs Wake-on-LAN. On a VisionMaster Pro2
  (firmware V02.01.00E.Q0718, 2026-10-29) both a power-off from the Android
  TV side and an IR remote power-off gave light standby; it was still
  answering 70 minutes and 10 minutes later respectively (longer
  measurements pending). In light standby `%1POWR 1` switches the
  projector on without Wake-on-LAN (verified from Home Assistant without a
  MAC address, 2026-10-29). The integration's *AWOL Link status* sensor
  records which depth the projector is in over time.
- UDP port 4352 is used for discovery (`%2SRCH` answered by `%2ACKN=...`).
  The official sheet leaves the `%2ACKN` value empty. Unlike standard PJLink
  class 2 it is NOT the MAC address but the projector's network name: a
  unicast `%2SRCH` to a VisionMaster Pro2 (on, firmware V02.01.00E.Q0718,
  over the VPN from another subnet, 2026-10-30) returned
  `%2ACKN=VisionMaster Pro2 x GoogleTV2891`. So the MAC address for
  Wake-on-LAN cannot be read over AWOL Link and must be entered by the user.

## Command format

`%<class><CODE> <value>` to set, `%<class><CODE> ?` to query. Replies are
`%<class><CODE>=OK`, `%<class><CODE>=<value>` or `%<class><CODE>=ERRn`.

| Error | Meaning |
| --- | --- |
| ERR1 | Undefined command, or feature not installed (only documented for `%2SVOL`: no speaker) |
| ERR2 | Invalid parameter |
| ERR3 | Command not available right now (for example gamma presets while an HDR signal is playing) |
| ERR4 | Projector malfunction |
| ERRA | Authentication failed |

## Commands

See `custom_components/valerion/lib/protocol.py` for the full list and
`models.py` for the value tables. Points worth knowing:

- `%1POWR`: `0` standby, `1` on, `2` off. This differs from standard PJLink.
  The VisionMaster Pro2 (firmware V02.01.00E.Q0718) refuses `%1POWR 2`
  with `ERR2` (2026-10-31), so it has no full off over AWOL Link.
- `%1AVMT`: `21` mute, `20` unmute. Audio only; the picture cannot be blanked.
- `%3PICL ?` lists the picture modes valid for the current signal; `%3PICT`
  sets one by its exact name (`HDR Theater`, `PC/Game`, `FILMMAKER MODE`).
- `%3GAMA`: `0`..`3` can be set (2.0, 2.2, 2.4, BT1886); `4` (SMPTE 2084)
  and `5` (HLG) only appear in HDR replies.
- `%3MOTN`: the command sheet and the response sheet disagree; the response
  sheet (`0` Off, `1` Custom, `2` Film, `3` Clear, `4` Standard, `5` Smooth)
  is used here. The VisionMaster Pro2 refuses `2` (Film) with `ERR2`
  in every format tested (see below).
- `%3ASPR` is query-only in the official list, but setting it works on the
  VisionMaster Max and the VisionMaster Pro2 while an HDMI signal is playing
  (see below).
- `%3LSMN ?`, `%3ZMMN ?`, `%3FCMN ?` are actions written as queries: they
  open the lens-shift, zoom and focus menus on screen and reply `OK`.

## Observed: VisionMaster Pro2, firmware V02.01.00E.Q0718 (2026-10-29)

Measured over Wi-Fi with no security code, the projector on and showing the
home screen (no HDMI signal). All documented queries were sent in one session.

- **Enabling:** only the switch on *All Settings > Inputs > External Inputs >
  AWOL Link* is needed. *Network IP Control Port* on the same menu can stay
  off. With AWOL Link off, the projector refuses every TCP connection
  ("connection refused") but still answers ping.
- **Greeting:** `PJLINK 0 ` with a trailing space.
- **Timing:** replies arrive in 0.04 to 0.15 s; 30 queries in one session
  worked without pauses.
- **Separators:** multi-value replies are separated by single spaces;
  only `%3PICL` uses commas.

| Query | Reply | Notes |
| --- | --- | --- |
| `%1POWR ?` | `1` | On |
| `%1INPT ?`, `%2INPT ?` | `30` | Home screen |
| `%1INST ?`, `%2INST ?` | `30 31 32 33` | Home, HDMI 1 to 3 |
| `%1NAME ?` | `VisionMaster` | |
| `%1INF1 ?` | `AWOL VISION` | |
| `%1INF2 ?` | `VisionMaster Pro2` | |
| `%1INFO ?` | `Elgant Grey` | Body colour, spelled this way by the firmware |
| `%1CLSS ?` | `2` | |
| `%2SVER ?` | `V02.01.00E.Q0718 83 OEM01.0.0.0` | Firmware, then two unexplained fields |
| `%2INNM ?` | `ERR2` | Not usable as a plain query |
| `%2IRES ?` | `0 x 0` | No signal |
| `%2RRES ?` | `3840 x 2160` | |
| `%2ERST ?` | `ERR1` | Not supported on this firmware |
| `%3VOLM ?` | `95` | |
| `%3PICL ?` | `Vivid,Standard,Sports,Energy Saving,Theater,FILMMAKER MODE` | SDR list; no `PC/Game` on the home screen |
| `%3PICT ?` | `FILMMAKER MODE` | |
| `%3LASL ?` | `10` | |
| `%3ENBL ?` | `3` | |
| `%3MOTN ?` | `0` | |
| `%3GAMA ?` | `1` | |
| `%3DYTM ?` | `0` | Answered, not ERR3, although no HDR10 signal was present |
| `%3CLTP ?` | `2` | |
| `%3ASPR ?` | `3` | |
| `%3SINF ?` | `0*0p@0Hz 0 255 3 0 0` | No signal (home screen). See [Signal information codes](#signal-information-codes-3sinf) |
| `%3FANS ?` | `1770 1710 0 0 0 0 0` | Seven fan slots, two in use |
| `%3TEMP ?` | `33 48 0 0 0 0 0 0` | Eight sensor slots, two in use |
| `%3LEDS ?` | `0` | Normal |

### In light standby (same projector, 2026-10-29)

A full survey with the projector in light standby (`%1POWR=0`, hours after
a power-off) answered every query, with the same timing. Differences from
the table above: `%3VOLM=0`, `%2SVER=V02.01.00E.Q0718 00 OEM01.0.0.0`
(second field `00` instead of `83`), `%3FANS=1800 1800 0 0 0 0 0`
(fans keep running) and `%3TEMP=35 45 0 0 0 0 0 0`. Identity queries
(`INF1`, `INF2`, `NAME`, `SVER`, `INST`) can therefore be read in light
standby.

## Observed with HDMI signals: VisionMaster Pro2, firmware V02.01.00E.Q0718 (2026-10-30)

Measured with SDR, HDR10 and Dolby Vision files played from a media player
on an HDMI input, through the integration's *Send raw command* action and
`scripts/awollink.py raw`. Every setting was put back afterwards.

| Signal | `%3SINF ?` | `%3PICL ?` |
| --- | --- | --- |
| SDR 1080p 24 Hz | `1920*1080p@24Hz 0 3 1 0 0` | `Vivid,Standard,Sports,Energy Saving,PC/Game,Theater,FILMMAKER MODE` |
| HDR10 4K 24 Hz | `3840*2160p@24Hz 0 3 1 1 2` | `HDR Vivid,HDR Standard,HDR Sports,HDR Energy Saving,HDR Game,HDR Theater,FILMMAKER MODE,IMAX Mode` |
| Dolby Vision 4K 24 Hz | `3840*2160p@24Hz 0 1 3 4 0` | `Dolby Vision Bright,Dolby Vision Dark,Dolby Vision Custom` |
| Dolby Vision 4K 60 Hz | `3840*2160p@60Hz 0 1 3 4 2` | same as 4K 24 Hz |

| Set command | SDR | HDR10 | Dolby Vision |
| --- | --- | --- | --- |
| `%3GAMA 0`..`3` | `OK`, read back | `ERR3` | `ERR3` |
| `%3GAMA 4` | `ERR3` | not tried | not tried |
| `%3DYTM 1`, `2` | `ERR3` | `OK`, read back | `ERR3` |
| `%3MOTN 0`, `1`, `3`, `4`, `5` | `OK` | `OK` | `OK` |
| `%3MOTN 2` | `ERR2` | `ERR2` | `ERR2` |
| `%3ASPR 0`..`9` | `OK`, each read back | `4` and `3`: `OK` | `4` and `3`: `OK`, the picture changed to 21:9 and back |
| `%3LASL 8` | | `OK`, read back | |
| `%3ENBL 1` | | | `OK`, read back |

- **A locked setting can still be read.** `%3GAMA ?` answers `1` (2.2) in
  Dolby Vision although gamma cannot be set there, and `4` (SMPTE 2084) in
  HDR10. `%3DYTM ?` answers in every format. Only a set command shows
  whether a setting is locked. Gamma is locked in HDR10 in every picture
  mode: *FILMMAKER MODE* (2026-10-30), then all eight HDR10 modes on
  2026-10-31 from the integration's gamma select (*HDR Theater* switched
  gamma to SMPTE 2084 by itself). Colour temperature, enhanced black level
  and dynamic tone mapping changes worked in HDR10 the same day.
  The integration builds in the locks measured here that also match
  AWOL's rule (dynamic tone mapping locked with SDR and Dolby Vision since
  v0.0.9, gamma with Dolby Vision since v0.0.9 and with HDR10 since
  v0.0.12; `lib/locks.py`) and learns any other `ERR3` on a set per signal
  format and picture mode. HLG and HDR10+ are not measured yet.
- **Aspect ratio:** without a signal the first Pro2 try (`%3ASPR 4`) replied
  `ERR2`, as reported for the Max.
- **Lens shift:** `%3LSMN ?` replied `ERR3` while playing Dolby Vision. The
  Pro2 most likely has no motorised lens shift; `%3ZMMN ?` opened the zoom
  menu (2026-10-29).

## Signal information codes (`%3SINF`)

The meaning of the six `%3SINF` fields is not in the official command list.
AWOL support sent this table to Michael Konieczki (VMote), who passed it on
on 2026-10-29. It matches every reply recorded on the Pro2 above (for
example SDR = PCM, 12-bit, YUV 4:2:2, SDR, BT.709; Dolby Vision = 8-bit RGB,
which is how Dolby Vision is carried over HDMI). The integration decodes the
fields with this table since v0.0.8.

Fields, in order: video timing (`3840*2160p@24Hz`), audio format, colour
depth, colour format, HDR format, colour primaries. `255` means unavailable
in every field.

| Field | Codes |
| --- | --- |
| Audio format | 0 PCM, 1 AAC, 2 HE-AAC, 3 Dolby Audio, 4 Dolby Atmos, 5 DTS, 6 DTS-HD, 7 DTS:X, 8 MP3, 9 FLAC, 10 WMA, 11 MPEG, 12 Other, 13 Multi |
| Colour depth | 0 6-bit, 1 8-bit, 2 10-bit, 3 12-bit, 4 16-bit |
| Colour format | 0 YUV 4:2:0, 1 YUV 4:2:2, 2 YUV 4:4:4, 3 RGB |
| HDR format | 0 SDR, 1 HDR10, 2 HLG, 3 HDR10+, 4 Dolby Vision |
| Colour primaries | 0 BT.709, 1 DCI-P3, 2 BT.2020 |

- **No signal:** AWOL says the whole reply is then `255`; the Pro2 on the
  home screen replied `0*0p@0Hz 0 255 3 0 0` instead. Both count as "no
  signal", and the other fields are ignored then (they claim PCM, RGB, SDR).
- **Audio 13 "Multi"** means the media has several audio tracks, not
  multichannel sound. Dolby TrueHD Atmos usually shows as 3 (Dolby Audio),
  not 4, because the projector cannot decode it.
- **Fans and temperatures:** `%3FANS` and `%3TEMP` report fixed slots (7 and
  8 on the Pro2) and fill only those in use (2 each on the Pro2). The
  temperature unit is not documented; 33 to 48 only makes sense as degrees
  Celsius.

## Reported: VisionMaster Max (Michael Konieczki, 2026-10-29)

Measured by Michael Konieczki on his VisionMaster Max (firmware not stated).
Not yet confirmed on the Pro2.

- **Standby:** after `%1POWR 0` the projector leaves the network within
  about 30 seconds (no greeting, no replies); light standby as on the Pro2
  was never seen. Wake-on-Wi-Fi shortly afterwards works every time, and the
  projector answers again after about 2 seconds.
- **Long standby:** after more than 24 hours it sometimes does not wake at
  all. Wi-Fi is then fully off and only the IR remote switches the
  projector on. The trigger is unknown; it seemed to depend on time, not on
  how the projector was switched off. Whether the Wi-Fi band (6 GHz versus
  2.4 GHz) matters is being tested.
- **Second connection:** accepted, but greeted only after the first one
  closes. While another app is connected, the projector therefore looks
  exactly like a projector in deep standby.
- **`%3ASPR <n>` sets the aspect ratio** for every value from `0` to `9`,
  and `%3ASPR ?` reads the new value back, but only while an HDMI signal is
  playing. On the home screen without a signal it is locked: a new value
  returns `ERR2`, re-sending the current value returns `ERR3`.

| `%3ASPR` | Aspect ratio |
| --- | --- |
| `0` | Auto |
| `1` | 4:3 |
| `2` | Zoom |
| `3` | 16:9 |
| `4` | 21:9 |
| `5` | 32:9 |
| `6` | Anamorphic 16:9 |
| `7` | Anamorphic 2.39:1 |
| `8` | Anamorphic 1.85:1 |
| `9` | Anamorphic 2.0:1 |

## Open questions (to be measured on real hardware)

- The `%3SINF` replies for HDR10+ and HLG signals, and for audio other
  than PCM.
- The `%3PICL` list for HDR10+ and HLG signals.
- The motion enhancement names the Pro2 shows in its own menu (it refuses
  `%3MOTN 2`, Film in both sheet tabs).
- Whether gamma can be set in HDR10 in picture modes other than
  *FILMMAKER MODE*.
- Which fan and temperature slots are filled on other models.
- What the extra `%2SVER` fields (`83`, `OEM01.0.0.0`) mean.
- Whether `%2ERST` is supported on other models or firmware.
- What *Status Notification* (an IPv4 address entered on the AWOL Link
  settings page) sends, and on which port. It may allow push updates instead
  of polling.
- Whether `%2SRCH` is answered while the projector is in standby (that would
  allow telling standby apart from "another controller is connected").
- Whether the Pro2 ever leaves light standby for a silent or unreachable
  state, and after how long.
