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
  answering 70 minutes and 2 minutes later respectively (longer
  measurements pending). The integration's *AWOL Link status* sensor
  records which depth the projector is in over time.
- UDP port 4352 is used for discovery (`%2SRCH` answered by `%2ACKN=...`).

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
- `%1AVMT`: `21` mute, `20` unmute. Audio only; the picture cannot be blanked.
- `%3PICL ?` lists the picture modes valid for the current signal; `%3PICT`
  sets one by its exact name (`HDR Theater`, `PC/Game`, `FILMMAKER MODE`).
- `%3GAMA`: `0`..`3` can be set (2.0, 2.2, 2.4, BT1886); `4` (SMPTE 2084)
  and `5` (HLG) only appear in HDR replies.
- `%3MOTN`: the command sheet and the response sheet disagree; the response
  sheet (`0` Off, `1` Custom, `2` Film, `3` Clear, `4` Standard, `5` Smooth)
  is used here.
- `%3ASPR` is query-only in the official list.
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
| `%3SINF ?` | `0*0p@0Hz 0 255 3 0 0` | Six fields; codes, not text labels. Meaning of the codes still to be measured with a signal |
| `%3FANS ?` | `1770 1710 0 0 0 0 0` | Seven fan slots, two in use |
| `%3TEMP ?` | `33 48 0 0 0 0 0 0` | Eight sensor slots, two in use |
| `%3LEDS ?` | `0` | Normal |

## Open questions (to be measured on real hardware)

- Meaning of the `%3SINF` codes (audio format, colour depth, colour format,
  HDR format, colour space) while an HDMI signal is playing, and the
  `%3PICL` lists for HDR10, HDR10+ and Dolby Vision.
- Which fan and temperature slots are filled on other models.
- What the extra `%2SVER` fields (`83`, `OEM01.0.0.0`) mean.
- Whether `%2ERST` is supported on other models or firmware.
- What *Status Notification* (an IPv4 address entered on the AWOL Link
  settings page) sends, and on which port. It may allow push updates instead
  of polling.
- Whether `%2SRCH` is answered while the projector is in standby (that would
  allow telling standby apart from "another controller is connected").
- Whether `%3ASPR <n>` sets the aspect ratio despite being undocumented.
- Behaviour of the second TCP connection: silently queued or dropped after a
  timeout.
