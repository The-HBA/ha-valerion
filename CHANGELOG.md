# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
