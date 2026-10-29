# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
