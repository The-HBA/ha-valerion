# Valerion projectors for Home Assistant

Local control of Valerion (AWOL Vision) projectors from Home Assistant over **AWOL Link**, the projector's own network control protocol. No cloud, no account, nothing leaves your network.

> **Special thanks to Michael Konieczki, creator of [VMote](https://play.google.com/store/apps/details?id=com.mkonieczki.vmote).**
> VMote is the unofficial Android remote for Valerion projectors and the proof that full local control was possible. Michael supported this project from the start and generously shared the hard-won details of how the projector really behaves on the wire (the security-code handshake, the single-session limit, Wake-on-LAN, which settings are locked in which picture format). Without his generosity this integration would have taken far longer to get right. If you have an Android phone, go get VMote.

Thanks also to [tinogo's Unfolded Circle driver](https://github.com/tinogo/uc-intg-awol-valerion), which served as a second reference for the protocol behaviour.

This is an independent community project. It is not affiliated with, endorsed by or supported by Valerion or AWOL Vision. AI-assisted tooling was used during development; every change is reviewed by the maintainer and tested against a real projector.

> **Status: early development.** Nothing is released yet. Follow the repository to be notified of the first release.

## What it does

| Home Assistant entity | What you get |
| --- | --- |
| Media player | State on / standby / off, power on (Wake-on-LAN) and off, input (Home, HDMI 1-3), volume, mute |
| Remote *(planned)* | Navigation keys, menu, settings, home, lens/zoom/focus menus |
| Selects *(planned)* | Picture mode (matching the current SDR/HDR/HDR10+/Dolby Vision format), gamma, dynamic tone mapping, colour temperature, enhanced black level, motion enhancement |
| Number *(planned)* | Laser brightness level |
| Sensor | *AWOL Link status* (diagnostic): answering, silent, refused or unreachable, so the history shows how deeply the projector sleeps in standby |
| More sensors *(planned)* | Input resolution, video/audio/HDR format, colour depth and space, aspect ratio, fan speeds, temperatures, LED/error status, firmware version |

## Compatibility

| | |
| --- | --- |
| Projectors | Valerion VisionMaster Pro2 (tested), Pro, Max, Plus2, Plus (AWOL Link is documented for all of them; reports welcome) |
| Projector firmware | V02.01.00E.Q0718 (August 2026) or newer, with AWOL Link enabled |
| Home Assistant | 2026.9 or newer |
| Network | The projector and Home Assistant on the same local network. Wake-on-LAN needs the projector's MAC address. |

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

Settings > Devices & services > Add integration > **Valerion**. Enter the IP address, the port (4352), the security code if you set one, and the MAC address. The projector must be on during setup.

## How it works

AWOL Link only allows **one control connection at a time**. If something holds that connection open, the Valerion app and VMote stop working. This integration therefore never keeps a connection: every poll and every command opens a short session, does its work and disconnects. While another app is connected the integration simply waits and shows the last known state.

Standby comes in two depths. In light standby the projector still answers, reports that it is in standby and can be switched on directly, without a MAC address. In deep standby it accepts network connections but does not answer them. Switching it on therefore sends a **Wake-on-LAN** packet to the MAC address you entered, then keeps asking the projector to power on until it answers. The *AWOL Link status* sensor shows which case applies: *answering*, *silent* (deep standby, or another app is connected), *refused* (AWOL Link is switched off on the projector) or *unreachable*.

## Known limitations

- Only the settings that AWOL Link documents are supported. Aspect ratio can be read but not set.
- Some settings are locked depending on the picture format (for example gamma presets in SDR only, dynamic tone mapping in HDR10 only). The projector reports these as unavailable.
- There is no play/pause/media information: AWOL Link does not expose the Android TV side of the projector.

## Troubleshooting

When opening an issue, please include: Home Assistant version, integration version, projector model and firmware, whether a security code is set, and the integration **diagnostics** download (device page > three dots > Download diagnostics). Enable debug logging from the integration page to capture the raw protocol exchange.

## Related projects

- [VMote](https://play.google.com/store/apps/details?id=com.mkonieczki.vmote), the Android remote by Michael Konieczki.
- [tinogo/uc-intg-awol-valerion](https://github.com/tinogo/uc-intg-awol-valerion), AWOL Link for Unfolded Circle remotes.
- [bruint/hacs-awol-link](https://github.com/bruint/hacs-awol-link), an earlier Home Assistant integration built from the published command tables.
- [Official AWOL Link article](https://support.valerion.com/hc/en-us/articles/17088458288143-What-is-AWOL-Link) with the command list.

## License

[MIT](LICENSE)
