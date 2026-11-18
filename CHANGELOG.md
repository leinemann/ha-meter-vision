# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-11-18

### Changed

- **The reading is now the median of the last 5 plausible readings**, not the last reading confirmed by
  the next one. A camera repeats its misreads, so a repeat confirmed them: replayed on two real days of a
  glitching water-meter camera, the old rule ended 1,031 L too high, with 80 true readings rejected as
  decreases. The median keeps the error at 0 L (5-minute rounds) to 17 L (15-minute rounds). The replay
  is a test now (`tests/test_field_corpus.py`).
- A reading above the growth gate (at most three intervals of the maximum increase) is `implausible`
  unless 5 readings in a row agree on it. `unconfirmed` now only means "no value yet".
- The reading sensor is `total` instead of `total_increasing`: the median can step back when a misread
  had briefly won, and that correction is subtracted instead of counted as a meter reset. Long-term
  statistics of an existing sensor carry on; Home Assistant may ask to confirm the state class change.
- The current reading is required when adding a meter.

### Added

- `docs/prior-art.md`: what users hit with AI-on-the-Edge and ha-ai-meter-reader, and what Meter Vision
  does about each.
- Setup guide: Claude, OpenAI, Kimi through OpenRouter, Gemini and a local Qwen vision model through
  Ollama as equal providers, and how to compare them on your own meter.

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
  wheels: each adds a decimal, and the first one widens the range when a rolling last wheel may already
  be on the higher number.
- Attributes `pointer_dials` on the reading sensor, `dials_read` and `last_wheel_rolling` on the last
  result sensor.
- Setup guide: camera options (ESP32-CAM with ESPHome, an AI-on-the-Edge device as a generic camera),
  AI providers (Claude, OpenAI, Kimi through OpenRouter, a local Qwen vision model through Ollama), model
  choice and cost per reading, comparing providers, mounting against glare and spiders.

### Changed

- Domain `meter_vision`, card `custom:meter-vision-card`, so it can be installed next to
  ha-ai-meter-reader.
