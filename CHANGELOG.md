# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-18

First release of Meter Vision, a fork of
[ha-ai-meter-reader](https://github.com/artech-lab/ha-ai-meter-reader) v1.0.1 by artech-lab. Everything
from that version is included: readings through any vision-capable AI Task entity, the plausibility
validator, the last-frame image, the problem alert, the read-now button and the bundled card.

### Added

- **Rolling last wheel.** The model reports when the last wheel is caught between two numbers and writes
  the lower one. A reading just below the accepted value but within one step of its last digit keeps the
  accepted value instead of being rejected as a decrease. An unreadable last wheel alone gives a lower
  bound instead of discarding the frame.
- **Pointer dials.** New *Pointer dials* option for the small `x0.0001`-style dials after the decimal
  wheels: each adds a decimal, and the first one tells which number a rolling last wheel is really on.
- Attributes `pointer_dials` on the reading sensor, `dials_read` and `last_wheel_rolling` on the last
  result sensor.
- Setup guide: camera options (ESP32-CAM with ESPHome, an AI-on-the-Edge device as a generic camera),
  Claude with your own API key, model choice and cost per reading, mounting against glare and spiders.

### Changed

- Domain `meter_vision`, card `custom:meter-vision-card`, so it can be installed next to
  ha-ai-meter-reader.
