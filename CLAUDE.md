# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project: Meter Vision

Fork of artech-lab/ha-ai-meter-reader v1.0.1 (GPL-3.0). Keep its SPDX headers; a modified file also carries
a `Based on … ha-ai-meter-reader v1.0.1` line, and `NOTICE.md` lists the changes.

Home Assistant custom integration (`custom_components/meter_vision`) that reads the counter of a water,
gas or energy meter from a camera frame through any AI Task entity, checks each reading for plausibility
and exposes a `total_increasing` sensor for the Energy dashboard. It bundles a dashboard card. Distributed
through HACS (category `integration`; from Home Assistant 2026.11 HACS is built in as the Marketplace).

Answer the maintainer in the language they write in. Code, comments, commit messages, entity IDs and the
README stay in English. User-facing strings exist in English and Italian.

## Commands

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements_test.txt   # once (Python 3.13)
scripts/check.sh                   # everything CI runs: ruff, card syntax, pytest
scripts/check.sh -k validator      # extra arguments go to pytest
```


## Layout

| Path | Content |
| --- | --- |
| `const.py` | Every constant: config keys, units and default maximum increase per unit, confirmations, AI retry and timeout |
| `reading.py` | Pure Python: AI prompt (English, short, numbered: written for small local vision models), output schema, parsing of the digits and pointer dials into a value plus tolerance |
| `validator.py` | Pure Python: `ReadingValidator`, the plausibility check (decrease beyond the reading's tolerance, allowed increase scaled by time, confirmation of jumps) |
| `monitor.py` | `MeterMonitor`: timer, light + camera frame, AI Task calls with fallback, alerts, storage |
| `messages.py` | Notification texts (en/it) |
| `entity.py`, `sensor.py`, `binary_sensor.py`, `button.py`, `image.py`, `number.py`, `switch.py` | Thin entities reading the monitor; they hold no logic |
| `config_flow.py` | Setup in two steps (meter type, then unit and sources) and one options form |
| `services.yaml` | The `set_reading` action, registered in `__init__.py` on the sensors of the integration |
| `frontend/meter-vision-card.js` | The card: one dependency-free ES module, no build step |
| `translations/en.json`, `it.json` | Integration strings (the card has its own `STRINGS` table) |
| `tests/` | `test_reading.py`, `test_validator.py` (pure), `test_monitor.py` (end to end on a real Home Assistant core with a fake AI Task service), `test_config_flow.py`, `test_consistency.py` |
| `scripts/make_icon.py` | Draws `brand/icon.png` and `icon@2x.png` from shapes (no fonts); re-run after changing the icon. |
| `scripts/preview.html` | The card with fictional demo values; `demo-frame.jpg` is a drawn meter (no photo), saved without metadata |

## Rules that keep it maintainable

- **One version**: `manifest.json` -> `version`. The integration appends it to the card URL
  (`?v=`), the card reads it from `import.meta.url`. Never hard-code it elsewhere (a test checks).
- **One release step**: pushing a new manifest version to `main` makes the `Release` job of
  `.github/workflows/validate.yml` create the tag and the GitHub release after all checks pass.
- **The model only copies digits.** No arithmetic, no decimal point, no comparison with previous values in
  the prompt: the decimal point, the digit count and every plausibility rule live in Python and are tested.
- **Readings are ranges.** `parse_reading()` returns the lowest value a frame is consistent with and a
  `tolerance` above it (one step of the last wheel or dial read). Never return a value that could be above
  the meter: a rolling wheel is read as its lower number, an unreadable last wheel as 0.
- **The reading is the median of the last `WINDOW_SIZE` plausible readings** (`validator.py`). It can step
  down when a misread had briefly won the majority, so the sensor is `total`, not `total_increasing`.
  Never go back to "accept a jump once the next reading confirms it": `tests/test_field_corpus.py` replays
  two real days of a glitching camera where that ends 1 m³ high. Any change to the validator must keep
  that test passing; `docs/prior-art.md` records why each rule exists.
- **The current reading is required at setup**: starting from nothing locks onto clustered misreads.
- **No numeric bounds in the AI output schema** (some providers reject `minimum`/`maximum`): the range
  is enforced by `parse_reading()`.
- **Unit and meter type are fixed at setup**: they define the statistics of the reading sensor.
- **Logic only in `reading.py`, `validator.py` and `monitor.py`**. The card displays what the integration
  computes (consumption figures are differences of the reading history) and discovers its entities from
  the device of the reading sensor (`translation_key` -> role in `SIBLINGS`).
- **Translations**: a new string goes in both `en.json` and `it.json`, in both languages of `STRINGS` in
  the card, or in both languages of `messages.py` (tests compare the key sets). Entity IDs are always
  English: `entity.py` sets them from the entry title and the description key.
- A new entity needs: a description in its platform file, a name in both translation files and an icon
  in `icons.json` (a test checks both) and, if the card shows it, an entry in the card's `SIBLINGS`.
- Options: do not add new ones without a strong reason; values that users tune while watching the card
  are entities (number, switch), not options.
- No personal data in the repository (names, e-mail addresses, entity IDs or device names of a real
  installation). Demo values are fictional; images carry no metadata (EXIF, comments, JFIF header).
- License: GPL-3.0-or-later. New source files start with `# SPDX-License-Identifier: GPL-3.0-or-later`.
