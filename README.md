# Meter Vision

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![GitHub release](https://img.shields.io/github/v/release/leinemann/ha-meter-vision)](https://github.com/leinemann/ha-meter-vision/releases)
[![Validate](https://github.com/leinemann/ha-meter-vision/actions/workflows/validate.yml/badge.svg)](https://github.com/leinemann/ha-meter-vision/actions/workflows/validate.yml)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)

**Read water, gas and electricity meters with a camera and the vision model of your choice.**

Point a camera at the counter, let a vision model copy the digits, and get a reading sensor ready for
the Energy dashboard. Every reading is checked before it is used, so a misread digit never reaches your
statistics. There's no cloud service of its own and no extra Python dependencies. Readings go through
Home Assistant's built-in [AI Task](https://www.home-assistant.io/integrations/ai_task/), so any AI Task
entity that reads images works, with your own key or none at all:

| Provider | Home Assistant integration | Notes |
| --- | --- | --- |
| Claude (Anthropic) | [Anthropic](https://www.home-assistant.io/integrations/anthropic/) | Your own API key. |
| OpenAI (GPT models) | [OpenAI](https://www.home-assistant.io/integrations/openai_conversation/) | Your own API key. |
| Kimi (Moonshot AI) and many others | [OpenRouter](https://www.home-assistant.io/integrations/open_router/) | One key for many providers; pick a model that takes images. |
| Google Gemini | [Google Generative AI](https://www.home-assistant.io/integrations/google_generative_ai_conversation/) | Your own API key. |
| Local Qwen-VL, Gemma, LLaVA… | [Ollama](https://www.home-assistant.io/integrations/ollama/) | Runs on your own hardware: no key, no cost per reading. |

Two providers can be combined: a main AI Task entity and a fallback, for example a local model with a
cloud model behind it.

> **New here? Read the [setup guide](docs/setup-guide.md).** It covers the camera options (ESP32-CAM with
> ESPHome, or an AI-on-the-Edge device you already have), each AI provider, model choice and cost per
> reading, and mounting the camera without glare or spiders.

## Why another meter reader

Classic on-device OCR (AI-on-the-Edge) works well until it doesn't. A reflection or a wheel caught between
two numbers can turn `140.925 m³` into `1139.93` or `11140.93`, and once such a value is in a
`total_increasing` sensor the statistics are wrong for good. Meter Vision does three things differently:

- **A large vision model reads the frame.** It sees the whole meter the way a person does, not a set of
  fixed digit boxes, and says when it is unsure.
- **A strict plausibility check sits between the model and your statistics.** A counter never goes
  back and only grows so fast. Large jumps wait for confirmation, and impossible ones are never accepted.
- **The last wheel is allowed to move.** It turns all the time, so it is often caught between two
  numbers. Meter Vision treats that as a normal reading with one step of tolerance instead of discarding
  the frame or flagging a decrease. An optional **pointer dial** (for example the `x0.0001` dial on many
  water meters) adds a decimal and tells which of the two numbers the wheel is really on.

## How it works

```text
timer → (light on, warm-up) → frame → (light off) → AI Task: "copy the digits" → checks → reading
```

- **Reading.** At every interval (15 minutes by default) the integration takes one frame and asks your
  AI Task entity to copy the wheels, from left to right. The model marks any wheel it cannot read with `X`,
  says whether the last wheel is between two numbers, reads the pointer dials if you have them and rates
  its confidence. It never calculates: the decimal point and every check are applied in Python.
- **Checks.** Unreadable wheels, low confidence or too many digits mean the frame is discarded and retried
  once. Only an unreadable *last* wheel is still used, as a lower bound. Then the value must make sense
  (see [Plausibility rules](#plausibility-rules)).
- **Energy dashboard.** The reading is a `total_increasing` sensor with the device class (water, gas or
  energy) and unit of the meter.
- **Alerts.** After three failed readings in a row the *problem* sensor turns on and you get a
  notification. It clears by itself with the next good reading.
- **Dashboard card.** It is served and loaded by the integration itself: there's no dashboard resource to
  add.

## Requirements

- Home Assistant 2025.8 or newer.
- A camera entity that shows the counter. See [camera options](docs/setup-guide.md#1-the-camera).
- An AI Task entity that reads images, from any of the providers above. See
  [the AI model](docs/setup-guide.md#2-the-ai-model) and [model and cost](docs/setup-guide.md#3-model-and-cost).

## Installation

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=leinemann&repository=ha-meter-vision&category=integration)

1. In HACS (the *Marketplace* from Home Assistant 2026.11), open the ⋮ menu → *Custom repositories*, and add
   `https://github.com/leinemann/ha-meter-vision` with type **Integration**.
2. Search for **Meter Vision**, download it and restart Home Assistant.

Manual alternative: copy `custom_components/meter_vision` into your `custom_components` folder and
restart.

## Setup

[![Open your Home Assistant instance and start setting up Meter Vision.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=meter_vision)

*Settings → Devices & services → Add integration → Meter Vision*. Add one entry per meter.

| Field | Description |
| --- | --- |
| Meter type | Water, gas, or electricity or heat. |
| Name | Device name and prefix of the entity IDs (default `Water meter`, `Gas meter` or `Energy meter`). |
| Unit of the counter | `L`, `m³`, `gal`, `ft³`, `CCF` for water; `m³`, `ft³`, `CCF` for gas; `kWh`, `Wh`, `MWh`, `GJ` for energy. It can't be changed later. |
| Camera | Shows the counter. |
| Camera light | Optional. Turned on for each frame and off right after. Leave it empty if the camera fires its own flash. |
| AI Task entity | Must read images. |
| Digits of the counter | How many wheels the AI must read, leading zeros and red decimal wheels included, pointer dials not. `0` = don't check. Recommended. |
| Decimal digits | How many of the last wheels are after the decimal point (often red). |
| Pointer dials | Small round dials with a pointer after the decimal wheels (`x0.0001`, `x0.001`, …), each one more decimal. `0` = none. |
| Current reading | Optional. The value on the meter now: the first reading is then accepted at once. Without it, two consistent readings are needed. |

Examples for a water meter with 5 black and 3 red wheels showing `00140925` and a `x0.0001` dial
pointing at 7:

| Unit | Digits | Decimal digits | Pointer dials | Reading |
| --- | --- | --- | --- | --- |
| `m³` | 8 | 3 | 1 | 140.9257 m³ |
| `m³` | 8 | 3 | 0 | 140.925 m³ |
| `L` | 8 | 0 | 0 | 140925 L |

Then add the card (*Add card → Meter Vision*, it finds its entities by itself) and, optionally, add the
reading sensor to *Settings → Dashboards → Energy → Water consumption* (or gas or grid).

```yaml
type: custom:meter-vision-card
entity: sensor.water_meter_reading
```

### Options

*Settings → Devices & services → Meter Vision → Configure*:

| Option | Default | Description |
| --- | --- | --- |
| Camera, light, AI Task entity | — | As in the setup. |
| Fallback AI Task entity | — | Used when the main one is unavailable or fails. |
| Digits, decimal digits, pointer dials | — | As in the setup. Changing the decimals or dials changes the scale of the next readings: set the reading by hand afterwards. |
| Reading interval | 15 min | How often the meter is read. Every reading is one AI call: see [cost](docs/setup-guide.md#3-model-and-cost). |
| Light warm-up | 30 s | Wait between light on and frame. Cameras with automatic exposure need 20–30 s or the frame is dark. |
| Notes about the meter | — | Anything peculiar about the counter, added to the AI instructions, for example *"the wheels are white on black; ignore the serial number above them"*. |
| Notification services | — | `notify.*` actions that receive the alert, for example the mobile app. |
| Persistent notifications | on | Also show the alert in Home Assistant. |

### Card options

| Option | Default | Description |
| --- | --- | --- |
| `entity` | — | **Required.** The reading sensor. |
| `name` | device name | Card title. |
| `show_counter` | `true` | The reading drawn as a meter counter; decimal wheels in red. |
| `show_consumption` | `true` | Consumption of today, yesterday and the last 24 hours. |
| `show_chart` | `true` | Hourly consumption of the last 24 hours. |
| `show_frame` | `true` | The last frame sent to the AI, with the digits it read. Tap to expand. |
| `show_result` | `true` | The result of the last reading and its confidence. |
| `show_buttons` | `true` | Read now, and automatic reading on/off. |

## Entities

Entity IDs are always in English (shown here with the default name). Displayed names follow the
language of Home Assistant (English and Italian).

| Entity | Description |
| --- | --- |
| `sensor.water_meter_reading` | The accepted reading: `total_increasing`, device class and unit of the meter. Attributes: `updated_at`, `pending_value` (a larger reading waiting for confirmation), `meter_type`, `digits`, `decimal_places`, `pointer_dials` and the source entities. |
| `sensor.water_meter_last_result` | `accepted`, `unconfirmed`, `decrease`, `implausible`, `unreadable`, `wrong_digits`, `error`, `corrected`. Attributes: `digits_read`, `dials_read`, `last_wheel_rolling`, `consecutive_failures`, `ai_engine`, `last_error`. |
| `sensor.water_meter_confidence` | Confidence 0–10 of the last answer. |
| `sensor.water_meter_last_read` | Time of the last reading attempt. |
| `sensor.water_meter_value_read` | Diagnostic: the last value read by the AI, even if rejected. |
| `image.water_meter_last_frame` | The frame of the last reading attempt. |
| `binary_sensor.water_meter_problem` | `on` after three failed readings in a row. |
| `binary_sensor.water_meter_reading_in_progress` | `on` while a reading runs. |
| `button.water_meter_read_now` | Reads the meter now. |
| `switch.water_meter_automatic_reading` | Readings at every interval (the button works either way). |
| `number.water_meter_max_increase` | Largest increase accepted between two readings one interval apart; more needs confirmation. The default depends on the unit (for example 300 L, 0.3 m³ of water, 1 m³ of gas, 5 kWh). |

The frame is also kept in the media folder (`meter_vision/water_meter.jpg`), never under `/config/www`.

### Action `meter_vision.set_reading`

Sets the reading by hand: after replacing the meter, to fix a wrong value or to start from a known one.
Target any sensor of the meter.

```yaml
action: meter_vision.set_reading
target:
  entity_id: sensor.water_meter_reading
data:
  value: 140.9257
```

## Plausibility rules

Each frame gives a range: the value read, and how far above it the meter may really be (one step of the
last wheel or dial read, ten steps when only the last wheel was unreadable).

| New reading compared with the accepted value | Result |
| --- | --- |
| Equal or higher, up to the allowed increase | `accepted` |
| Lower, but within its own range (the last wheel between two numbers) | `accepted`: the accepted value is kept, never lowered |
| Lower by more than that | `decrease`: rejected |
| Higher than the allowed increase | `unconfirmed`: kept aside, accepted when the next reading is consistent with it |
| Higher than a whole day at the maximum increase (or than the time since the last accepted value at that rate, if longer) | `implausible`: rejected however many readings agree. Fix the value with `meter_vision.set_reading` if it is real |
| Any wheel but the last marked unreadable, confidence below 4, or too many digits | `unreadable` / `wrong_digits`: the frame is retried once, then rejected |

The allowed increase is the *maximum increase per reading* multiplied by the number of intervals since
the last accepted value (at least one). If your meter can run faster than the default (a pool fill, a
garden hose), raise it from the device page.

### The rolling last wheel and the pointer dial

The model writes the *lower* number of a wheel caught between two numbers and reports
`last_wheel_rolling`. Without a dial the true value is somewhere between that number and the next one,
which the validator allows for. With a dial, the wheel turns while the first dial passes from 9 to 0:
when the wheel is rolling and the dial reads 0, 1 or 2, the wheel may already be on the higher number,
so the range is widened by one wheel step. The value itself is never raised on the model's word: a
wrongly set rolling flag must not push the reading above the meter.

## Troubleshooting

- **The card is not in the card picker.** Reload the browser page once after installing or updating.
- **Readings stay `unconfirmed`.** The meter runs faster than the maximum increase per reading, or the AI
  keeps reading a different number. Check the last frame and raise the maximum increase.
- **Readings are `decrease`.** Usually a misread wheel. If the accepted reading is really too high, set the
  correct value with `meter_vision.set_reading`.
- **Readings are `error`.** See the `last_error` attribute of the last result sensor. The AI Task entity
  must support attachments and structured output, and the model must take images.
- **The dial is never read.** `dials_read` on the last result sensor shows what the model returned, and
  the log says when the dials were unreadable and only the wheels were used.
- **Something else.** Attach the diagnostics (*device page → ⋮ → Download diagnostics*) to a
  [new issue](https://github.com/leinemann/ha-meter-vision/issues).

## Contributing

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements_test.txt
scripts/check.sh
```

The version lives only in `manifest.json`. Pushing a new one to `main` publishes the release once the
checks pass. See [`CLAUDE.md`](CLAUDE.md) for the layout of the code.

## Credits and license

Meter Vision is a fork of [**ha-ai-meter-reader**](https://github.com/artech-lab/ha-ai-meter-reader) by
[artech-lab](https://github.com/artech-lab), version 1.0.1. Its design and most of its code come from
there: the AI Task reading, the plausibility validator, the entities, the alerts and the dashboard card.
Thank you. Meter Vision renamed it (domain `meter_vision`) so both can be installed side by side, and
added the rolling last wheel, pointer dials and the setup guide. See [`NOTICE.md`](NOTICE.md) for what
was changed.

Copyright © 2026 The ha-ai-meter-reader contributors and the ha-meter-vision contributors. Released
under the [GNU General Public License v3.0 or later](LICENSE).

Not affiliated with or endorsed by Anthropic, OpenAI, Moonshot AI, Alibaba, Ollama or Home Assistant.
