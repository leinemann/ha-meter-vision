# Notice

Meter Vision is a modified version of **ha-ai-meter-reader** v1.0.1
(<https://github.com/artech-lab/ha-ai-meter-reader>, commit `20905394`), Copyright © 2026 The
ha-ai-meter-reader contributors, licensed under the GNU General Public License v3.0 or later.
It is distributed under the same licence (see [`LICENSE`](LICENSE)).

## Changes made (2026-11-18, ha-meter-vision v0.1.0)

- Renamed the integration: domain `ai_meter_reader` → `meter_vision`, name "AI Meter Reader" →
  "Meter Vision", card `ai-meter-reader-card` → `meter-vision-card`, so both can be installed together.
- `reading.py`: the model reports whether the last wheel is between two numbers (`last_wheel_rolling`)
  and is told never to mark such a wheel unreadable. Readings carry a tolerance. An unreadable last
  wheel alone gives a lower bound instead of a rejected frame. Optional pointer dials
  (`pointer_dials` option) add decimals and resolve a rolling last wheel.
- `validator.py`: a reading lower than the accepted value but within its own tolerance keeps the
  accepted value instead of counting as a decrease.
- `monitor.py`, `config_flow.py`, `sensor.py`, `number.py`, translations and card: the pointer-dial
  option, the precision it adds, and the new attributes.
- New tests for the above; documentation rewritten, with a setup guide in `docs/`.

Files carry a `Based on … ha-ai-meter-reader v1.0.1` line where they were modified; unmodified files keep
the original SPDX header only.
