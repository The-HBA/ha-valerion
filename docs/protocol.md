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
- In standby the projector accepts TCP connections but never sends the
  greeting. Power-on from standby needs Wake-on-LAN.
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

## Open questions (to be measured on real hardware)

- Exact reply format of `%3SINF`, `%3FANS`, `%3TEMP`, `%3PICL` and `%2SVER`
  (newline, space or comma separated).
- Round-trip time per command and the practical number of commands per
  session.
- Whether `%2SRCH` is answered while the projector is in standby (that would
  allow telling standby apart from "another controller is connected").
- Whether `%3ASPR <n>` sets the aspect ratio despite being undocumented.
- Behaviour of the second TCP connection: silently queued or dropped after a
  timeout.
