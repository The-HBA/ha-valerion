# Valerion projectors for Home Assistant

Local control of Valerion (AWOL Vision) projectors from Home Assistant over **AWOL Link**, the projector's own network control protocol. No cloud, no account, nothing leaves your network.

> **Special thanks to Michael Konieczki, creator of [VMote](https://play.google.com/store/apps/details?id=com.mkonieczki.vmote).**
> VMote is the unofficial Android remote for Valerion projectors and the proof that full local control was possible. Michael supported this project from the start and generously shared the hard-won details of how the projector really behaves on the wire (the security-code handshake, the single-session limit, Wake-on-LAN, which settings are locked in which picture format). Without his generosity this integration would have taken far longer to get right. If you have an Android phone, go get VMote.

Thanks also to [tinogo's Unfolded Circle driver](https://github.com/tinogo/uc-intg-awol-valerion), which served as a second reference for the protocol behaviour.

This is an independent community project. It is not affiliated with, endorsed by or supported by Valerion or AWOL Vision. The Valerion and AWOL names and logos belong to their owners and are used only to identify the supported projectors. AI-assisted tooling was used during development; every change is reviewed by the maintainer and tested against a real projector.

> **Status: early development.** Development releases (0.0.x) are available and tested on a VisionMaster Pro2; v0.1.0 will be the first complete version. Follow the repository to be notified of new releases.

## What it does

| Home Assistant entity | What you get |
| --- | --- |
| Media player | State on / standby / off, power on (Wake-on-LAN) and off, input (Home, HDMI 1-3), volume, mute |
| Remote | Sends the remote keys by name with `remote.send_command` (see [Remote keys](#remote-keys)); on/off switches the projector |
| Buttons | *Lens shift menu*, *Zoom menu*, *Focus menu* (open the menu on screen). The navigation keys (up, down, left, right, OK, return, menu, settings, home) are also buttons, disabled by default; enable them on the device page if you want them on a dashboard. *Forget learned locks* (Configuration, disabled by default) |
| Selects | *Picture mode* (the list matches the current SDR/HDR/HDR10+/Dolby Vision format), *Aspect ratio* (Auto, 4:3, Zoom, 16:9, 21:9, 32:9 and four anamorphic ratios; can only be changed while an HDMI signal is playing); under Configuration: *Gamma*, *Dynamic tone mapping*, *Color temperature*, *Enhanced black level*, *Motion enhancement*. A setting that is locked for the current signal and picture mode shows as unavailable (see [Locked settings](#locked-settings)) |
| Number | *Laser level* (0-10 slider) |
| Sensors | *Video signal* (for example 3840×2160p 24 Hz) and *HDR format* (SDR, HDR10, HLG, HDR10+, Dolby Vision or no signal). Diagnostic: *Audio format*, *Color depth*, *Color format*, *Color primaries*, *LED status*, one *Fan* and *Temperature* sensor per fan and temperature sensor the projector reports (added automatically the first time it reports a value), and *AWOL Link status*: answering, silent, refused or unreachable, so the history shows how deeply the projector sleeps in standby |
| Binary sensor | *Problem* (diagnostic): on when the LED status is anything other than normal (overtemperature, fan error and so on), for alerts in automations |

## Compatibility

| | |
| --- | --- |
| Projectors | Valerion VisionMaster Pro2 (tested), Pro, Max, Plus2, Plus (AWOL Link is documented for all of them; reports welcome) |
| Projector firmware | V02.01.00E.Q0718 (August 2026) or newer, with AWOL Link enabled |
| Home Assistant | 2026.9 or newer |
| Network | Home Assistant must reach the projector's IP address (TCP port 4352). The projector may sit on another network (VLAN); then allow TCP 4352 and UDP 9 (Wake-on-LAN) from Home Assistant to the projector. Wake-on-LAN needs the projector's MAC address. |

## Before you start

1. On the projector: open **All Settings > Inputs > External Inputs > AWOL Link** and switch **AWOL Link** on. Optionally set a security code on the same page. (The *Network IP Control Port* switch is not needed.)
2. Set the projector's menu language to **English (US)**. In other languages the projector refuses some colour-temperature values (a known firmware bug).
3. Give the projector a fixed IP address in your router (DHCP reservation).
4. Note the MAC address from **All Settings > System > About > Status**. It is needed to switch the projector on from standby.

## Installation

### Marketplace / HACS (recommended)

Until this integration is part of the default catalog, add it as a custom repository:

[![Open your Home Assistant instance and add this repository.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=The-HBA&repository=ha-valerion&category=integration)

Or manually: open HACS (Settings > Marketplace from Home Assistant 2026.11), choose *Custom repositories*, add `https://github.com/The-HBA/ha-valerion` with category *Integration*, download **Valerion**, then restart Home Assistant.

### Manual

Copy the `custom_components/valerion` folder into the `custom_components` folder of your Home Assistant configuration directory and restart Home Assistant.

## Setup

Settings > Devices & services > Add integration > **Valerion**. Enter the IP address, the port (4352), the security code if you set one, and the MAC address. The projector must be on or in standby during setup; if it does not answer in standby, switch it on.

The MAC address can be added, changed or removed later: Settings > Devices & services > Valerion, then the settings (gear) button next to the projector. Saving reloads the projector; entity names and history stay as they are.

## Remote keys

Send keys with the `remote.send_command` action to the projector's remote entity. Names are not case sensitive:
`up`, `down`, `left`, `right`, `ok`, `return`, `menu`, `settings`, `home`, `volume_up`, `volume_down`, `lens_shift`, `zoom`, `focus`.
Several keys in one call, *Repeats* and *Delay between commands* are supported; a whole sequence uses one short connection. Keys are only sent while the projector is on.

```yaml
action: remote.send_command
target:
  entity_id: remote.visionmaster_pro2_remote
data:
  command: [down, down, ok]
  delay_secs: 0.5
```

## Actions

**Valerion: Send raw command** (`valerion.send_raw_command`) sends one AWOL Link line to the projector and returns its reply, for example `%1POWR ?` returns `%1POWR=1`. It is meant for testing and for commands that have no entity yet; see AWOL's command list for the codes. Error replies are returned as they are (`ERR2` invalid value, `ERR3` not available for the current signal). The *Projector* field can stay empty when only one projector is set up.

```yaml
action: valerion.send_raw_command
data:
  command: "%3ASPR ?"
response_variable: reply
```

## How it works

AWOL Link only allows **one control connection at a time**. If something holds that connection open, the Valerion app and VMote stop working. This integration therefore never keeps a connection: every poll and every command opens a short session, does its work and disconnects. While another app is connected the integration simply waits and shows the last known state.

Standby differs between models. In light standby (seen on the VisionMaster Pro2) the projector still answers, reports that it is in standby and can be switched on directly, without a MAC address. In deep standby it either accepts network connections without answering them, or leaves the network altogether (the VisionMaster Max does this about 30 seconds after switching off). Switching it on therefore sends a **Wake-on-LAN** packet to the MAC address you entered, both as a broadcast (reaches a projector on Home Assistant's own network) and straight to the projector's IP address (also crosses to another VLAN), and repeats it every few seconds while it keeps asking the projector to power on, for up to 45 seconds. The *AWOL Link status* sensor shows which case applies: *answering*, *silent* (deep standby, or another app is connected), *refused* (AWOL Link is switched off on the projector) or *unreachable* (off, or in a standby that leaves the network).

## Locked settings

Some picture settings cannot be changed with certain signals: in Dolby Vision, for example, gamma is fixed. The projector still reports a value for a locked setting, so Home Assistant cannot see the lock until a change is refused. The integration therefore combines two kinds of locks, and a locked setting shows as unavailable while its signal format (SDR, HDR10, HLG, HDR10+, Dolby Vision) and picture mode are active:

- **Built-in locks**, the same for everyone, measured on the VisionMaster Pro2 and matching AWOL's own description: *Dynamic tone mapping* is locked with SDR and Dolby Vision, *Gamma* with Dolby Vision.
- **Learned locks**: when the projector refuses a change because the setting is locked (`ERR3`), Home Assistant remembers it for that signal format and picture mode, so the next time the setting is unavailable at once. This covers models, formats and picture modes that are not built in yet. Learned locks are kept across restarts and forgotten after a firmware update, which may unlock settings.

If a setting ever stays unavailable when it should not, enable the *Forget learned locks* button on the device page (Configuration) and press it. The diagnostics download lists the locks in effect; sharing it in an issue helps turn learned locks into built-in ones.

## Known limitations

- The integration only uses commands from AWOL's official command list, with one exception: the list documents aspect ratio as read-only, but setting it works while an HDMI signal is playing. This was tested on the VisionMaster Pro2 (all ten values with SDR, HDR10 and Dolby Vision, firmware V02.01.00E.Q0718) and on the VisionMaster Max (by Michael Konieczki). Without a signal the projector refuses the change.
- The meaning of the signal codes (audio format, colour depth and so on) is not in AWOL's public command list; it comes from AWOL support via Michael Konieczki and matches every reply tested on the VisionMaster Pro2. Dolby TrueHD Atmos usually shows as *Dolby Audio*, because the projector cannot decode it, and *Several audio tracks* means the media has more than one audio track, not multichannel sound. The temperature unit is not documented; the values only make sense as degrees Celsius.
- On another VLAN, the Wake-on-LAN packet sent to the projector's IP address only arrives while the router still remembers the projector's MAC address (usually several minutes to hours after it left the network). For a projector that leaves the network in standby, add a static ARP entry for it on the router (OPNsense and pfSense offer this in the DHCP static mapping).
- AWOL Link cannot report the projector's MAC address: the UDP search reply contains the projector's network name instead, so the MAC has to be entered by hand.
- After a long standby (more than a day), some projectors switch Wi-Fi off completely. Wake-on-LAN cannot reach them then, and only the IR remote switches them on (seen on the VisionMaster Max).
- Some settings are locked depending on the picture format (for example gamma presets in SDR only, dynamic tone mapping in HDR10 only). A lock that is neither built in nor learned yet shows up only when a change is refused; the setting is then shown as unavailable for that format and picture mode (see [Locked settings](#locked-settings)).
- Not every model has every feature. The VisionMaster Pro2, for example, refuses the *Film* motion enhancement mode and the lens shift menu; Home Assistant then shows a message explaining why.
- Picture settings are read about once a minute (and at once after a change from Home Assistant or a picture-mode change), so a change made with the IR remote can take up to a minute to show.
- *Warm 1* and *Warm 2* colour temperature only work when the projector's menu language is English (US); this is a known firmware issue.
- There is no play/pause/media information: AWOL Link does not expose the Android TV side of the projector.

## Troubleshooting

When opening an issue, please include: Home Assistant version, integration version, projector model and firmware, whether a security code is set, and the integration **diagnostics** download (device page > three dots > Download diagnostics). Enable debug logging from the integration page to capture the raw protocol exchange.

## Related projects

- [VMote](https://play.google.com/store/apps/details?id=com.mkonieczki.vmote), the Android remote by Michael Konieczki.
- [tinogo/uc-intg-awol-valerion](https://github.com/tinogo/uc-intg-awol-valerion), AWOL Link for Unfolded Circle remotes.
- [Official AWOL Link article](https://support.valerion.com/hc/en-us/articles/17088458288143-What-is-AWOL-Link) with the command list.

## License

[MIT](LICENSE)
