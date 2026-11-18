# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.2] - 2026-11-18

### Fixed

- **A light that is already on is left alone.** A reading used to turn the light to full brightness and then
  off, even when someone had it on. Now a light that is on is used as it is and never switched off.
- **An unexpected error in a camera or AI integration counts as a failed reading.** Until now an exception
  other than the usual Home Assistant ones ended the reading without recording it: no failure was counted,
  so the problem alert never fired. It is now logged with its traceback, shown as the last error and
  counted, and an AI engine that fails this way falls back to the fallback engine.

## [0.3.1] - 2026-11-18

### Changed

- **Own icon.** Meter Vision now has its own icon (a meter counter in a camera viewfinder), drawn from
  shapes by `scripts/make_icon.py`; until now the integration shipped ha-ai-meter-reader's icon.

### Fixed

- Labels on the annotated frame could be placed at fractional pixel positions with a FreeType font
  (Pillow's font size is a float). Found by the new type check.

### Development

- CI runs mypy and enforces 95% test coverage (98% at this release) in *Lint and tests*.
- CodeQL scans the Python, the card and the workflows on every pull request and weekly.
- The README shows a real annotated frame.

## [0.3.0] - 2026-11-18

### Added

- **Annotated last frame.** The *Last frame* image now shows what the model read: a banner with the
  result, the reading, the time and the digits read, and, with the new *Counter position* and *Dial
  positions* options, one box per wheel with its digit (coloured by confidence, unreadable digits crossed
  out in red) and a circle per dial. The boxes are equal slices of the counter position, not coordinates
  from the model, so they work with every provider. Drawn with Pillow, which ships with Home Assistant.
- *Frame sent to the AI* (`image.<name>_raw_frame`, diagnostic): the clean frame, for debugging and for
  building test sets.
- Changing the positions redraws the last frame at once, without a new reading.

## [0.2.0] - 2026-11-18

### Changed

- **The reading is now the median of the last 5 plausible readings**, not the last reading confirmed by
  the next one. A camera repeats its misreads, so a repeat confirmed them: replayed on two real days of a
  glitching water-meter camera, the old rule ended 1,031 L too high, with 80 true readings rejected as
  decreases. With the median the reading never leaves the true range (0 L error at 5- and 15-minute rounds). The replay
  is a test now (`tests/test_field_corpus.py`).
- The growth gate is measured from the newest plausible reading and capped at three intervals of the
  maximum increase. Readings rejected above it for two hours (at least 5, steadily agreeing) move the
  reading up: catching up after an outage, following a meter faster than the maximum increase. Readings
  rejected below for two hours only undo such a move, within a day. `unconfirmed` only means "no value at
  all" and now counts as a failure.
- The setup reading fills the window, so a single misread right after setup is outvoted too.
- A frame identical to the previous one is an error and isn't sent to the AI (frozen camera).
- Stored state that can't be read falls back to the setup reading instead of starting from nothing.
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
