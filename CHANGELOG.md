# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.0.13] - 2026-10-31

### Added
- Lens shift, zoom and focus menu buttons hide themselves on projectors without that menu. The first time the projector refuses a menu while it is on, Home Assistant remembers it, marks the button unavailable and hides it. *Forget learned locks* or a firmware update brings it back. Buttons you hid yourself are never touched.
- README: troubleshooting table with links to the fixes.

### Changed
- *Picture mode* and *Aspect ratio* moved to the Configuration section of the device page, next to the other picture settings. Names, entity IDs and history stay the same. Like the other Configuration entities, they no longer appear on the auto-generated Overview dashboard; add them to your own dashboard if you use them there.
- README: laser level, enhanced black level and color temperature results added to the signal table.

## [0.0.12] - 2026-10-31

### Added
- [Help test your projector](docs/help-test.md): tests for owners of models other than the VisionMaster Pro2, all done in Home Assistant, and a *Model test report* issue form.

### Changed
- *Gamma* is now a built-in lock for HDR10: it shows as unavailable in every HDR10 picture mode from the start. The projector refused gamma changes in all eight HDR10 picture modes on a VisionMaster Pro2. HLG and HDR10+ are not measured yet and are still learned.
- README: screenshots, and tables of which settings work with which signal and on which projector.

## [0.0.11] - 2026-10-31

### Changed
- The navigation key buttons (up, down, left, right, OK, return, menu, settings, home) are now enabled by default, ready for dashboards. When you update, the ones that were disabled by default are switched on once; any button you disabled yourself stays disabled. Home Assistant reloads the projector about 30 seconds after the first start, which is normal.

## [0.0.10] - 2026-10-30

### Added
- Settings (gear) button for each projector in Settings > Devices & services > Valerion. The MAC address for Wake-on-LAN can now be added, changed or removed after setup without deleting the projector. Entity names and history stay as they are.
- The diagnostics download shows whether a MAC address is set and the last Wake-on-LAN attempt.

### Changed
- Switching on sends the Wake-on-LAN packet both as a broadcast and straight to the projector's IP address, so it also reaches a projector on another network (VLAN). It is repeated every 6 seconds while Home Assistant waits for the projector to answer, because Wi-Fi in power-save mode can miss a single packet.
- The MAC address is no longer attached to the device in Home Assistant's device registry. The Android TV integrations register the same address, and Home Assistant would then try to merge the two devices.

## [0.0.9] - 2026-10-30

### Added
- Locked settings show as unavailable before you try them. The projector reports a value even for a setting it will not change (gamma reads 2.2 while Dolby Vision plays), so Home Assistant could not tell. Two sources now tell it:
  - Built-in locks, the same for every projector: *Dynamic tone mapping* is locked with SDR and Dolby Vision, *Gamma* with Dolby Vision.
  - Learned locks: when the projector refuses a change because the setting is locked, Home Assistant remembers it for that signal format and picture mode, also after a restart. Learned locks are forgotten after a firmware update.
- *Forget learned locks* button (Configuration, disabled by default) in case a setting was learned as locked by mistake.
- The diagnostics download lists the built-in and learned locks in effect.

## [0.0.8] - 2026-10-30

### Added
- *Video signal* sensor (resolution and refresh rate, for example 3840×2160p 24 Hz) and *HDR format* sensor (SDR, HDR10, HLG, HDR10+, Dolby Vision or no signal).
- Diagnostic sensors for *Audio format*, *Color depth*, *Color format*, *Color primaries* and *LED status*.
- One *Fan* and one *Temperature* sensor for each fan and temperature sensor the projector reports. They are added automatically the first time the projector reports a value, so each model gets its own number of sensors.
- *Problem* binary sensor: on when the LED status reports overtemperature, a fan error or another fault.
- The diagnostics download shows the decoded signal information.

## [0.0.7] - 2026-10-30

### Added
- *Aspect ratio* select: Auto, 4:3, Zoom, 16:9, 21:9, 32:9 and four anamorphic ratios. The projector accepts a change only while an HDMI signal is playing. Setting the aspect ratio is not in AWOL's official command list, but it was tested on the VisionMaster Pro2 and the VisionMaster Max.

### Changed
- Clearer error messages when the projector refuses a motion enhancement mode it does not offer (for example *Film* on the VisionMaster Pro2), an aspect ratio change without a signal, or a lens shift, zoom or focus menu its model does not support.

## [0.0.6] - 2026-10-30

### Added
- *Picture mode* select. The list of modes follows the current signal (SDR, HDR10, HDR10+, Dolby Vision) and is read again when the format changes.
- Selects for *Gamma*, *Dynamic tone mapping*, *Color temperature*, *Enhanced black level* and *Motion enhancement* (in the device's Configuration section).
- *Laser level* slider (0-10).
- Clear error messages when a setting is locked for the current signal, and when Warm 1 / Warm 2 is refused because the menu language is not English (US).

### Fixed
- A setting that is locked for the current signal now stays unavailable between polls instead of switching between unavailable and unknown.

## [0.0.5] - 2026-10-29

### Added
- *Remote* entity: send the projector's remote keys by name (`up`, `down`, `left`, `right`, `ok`, `return`, `menu`, `settings`, `home`, `volume_up`, `volume_down`, `lens_shift`, `zoom`, `focus`) with `remote.send_command`, including repeats and delays.
- Buttons for the lens shift, zoom and focus menus, plus one button per navigation key (disabled by default).
- *Send raw command* action (`valerion.send_raw_command`): sends one AWOL Link command line and returns the projector's reply.

### Changed
- When the projector rejects a command, the error message shows the full command line that was sent.

## [0.0.4] - 2026-10-29

### Changed
- Home Assistant now shows the official AWOL Valerion icon and logo (light and dark theme) instead of a generic projector icon.

## [0.0.3] - 2026-10-29

### Fixed
- The device page now shows the projector model and firmware even when Home Assistant started while the projector was in standby. The identity is read whenever the projector answers, also in standby, and the device page is corrected when it changes.
- The firmware version shows only the version itself (for example V02.01.00E.Q0718), without the extra fields that change between on and standby.

### Changed
- Setup texts: the projector can be on or in standby during setup, it does not need to be switched on.

## [0.0.2] - 2026-10-29

### Added
- *AWOL Link status* diagnostic sensor: answering, silent, refused or unreachable. Its history shows how deeply the projector sleeps in standby.
- Setup tells you when AWOL Link is switched off on the projector (connection refused) instead of a generic connection error.

### Changed
- The media player shows on, standby or off instead of only on or off.

## [0.0.1] - 2026-10-29

### Added
- AWOL Link protocol library with a command line tool for testing against a real projector.
- Setup through the Home Assistant UI, media player entity (power, input, volume, mute) and diagnostics.
