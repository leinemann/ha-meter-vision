# Prior art: what we learned, and what we do about it

Meter Vision exists because two good projects each solved half of the problem. This page records what
real users hit with them, so that the design follows from evidence instead of taste. It was written in
November 2026 from:

- [**AI-on-the-Edge**](https://github.com/jomjol/AI-on-the-edge-device): ESP32-CAM firmware that reads the
  meter on the device with small neural networks. Sources: its documentation (correction algorithm, FAQ,
  alignment, reference image, analog-to-digit transition) and its issues, searched by title. The repository
  has about 2,800 issues and pull requests; counts below are title matches and are rough. Its GitHub
  Discussions were not searched.
- [**ha-ai-meter-reader**](https://github.com/artech-lab/ha-ai-meter-reader) v1.0.1 by artech-lab: a Home
  Assistant integration that sends a camera frame to an AI Task entity. Meter Vision started as a fork of
  it, so all of its code was read: prompt, validator, monitor, card, tests, and its contributor notes.
- **Field data**: two days (16–18 November 2026) of an AI-on-the-Edge camera on a Ferro water meter,
  published every 5 minutes, in [`tests/fixtures`](../tests/fixtures). The true reading crept from
  140.911 to 140.923 m³. About a third of the 111 rounds were misreads: 139.93 and 141.94 (a whole-number
  wheel off by one), 1139.93 and 11140.93 (a phantom leading digit).

## What users hit with AI-on-the-Edge

| # | Failure | Evidence | Its mitigation, and where it falls short |
| --- | --- | --- | --- |
| 1 | **A wheel caught between two numbers** reads as `N`. The firmware fills it from the previous value, so a roll-over like 199 → 2NN becomes 299 and stays wrong. | Among the most-discussed issues: [#40](https://github.com/jomjol/AI-on-the-edge-device/issues/40), [#710](https://github.com/jomjol/AI-on-the-edge-device/issues/710), [#887](https://github.com/jomjol/AI-on-the-edge-device/issues/887) (40–66 comments each). | Consistency checks and "continuous" digit models. The FAQ admits roll-over states "might be false". Filling from the previous value causes the persistent errors. |
| 2 | **Analog-to-digit transition**: digits read correctly, combined value one unit off, because each meter flips its last wheel at a different pointer position. | [#2857](https://github.com/jomjol/AI-on-the-edge-device/issues/2857) (66 comments), [#921](https://github.com/jomjol/AI-on-the-edge-device/issues/921), [#2743](https://github.com/jomjol/AI-on-the-edge-device/issues/2743). | One per-meter parameter (`AnalogToDigitTransitionStart`), tuned by trial over days. |
| 3 | **PreValue, negative-rate and max-rate checks**: the main way readings get stuck or rejected in a loop. "Rate too high" on correct digits; the negative-rate check firing on 2e-5 of float noise; errors repeating after a manual correction; a relative rate letting a 1 m³ misread through after a quiet night; rejected values still reaching InfluxDB. | About 22 title matches for "rate too high", 14 for "negative rate", 11 for "prevalue", hundreds of comments: [#2903](https://github.com/jomjol/AI-on-the-edge-device/issues/2903), [#3143](https://github.com/jomjol/AI-on-the-edge-device/issues/3143), [#643](https://github.com/jomjol/AI-on-the-edge-device/issues/643). | `MaxRateValue`, `AllowNegativeRates` and a force-accept after a timeout so it "can not run in an endless error". The FAQ names the trade-off itself: fewer wrong values means stale values for hours. |
| 4 | **Decimal shift errors** between the digit and pointer parts. | [#2887](https://github.com/jomjol/AI-on-the-edge-device/issues/2887) (52 comments). | A proposed fix; not checked whether it was merged. |
| 5 | **Pointer misreads**, worst near zero, which is exactly where transitions are decided. A model update made it worse. | About 74 title matches for "analog": [#3702](https://github.com/jomjol/AI-on-the-edge-device/issues/3702), [#434](https://github.com/jomjol/AI-on-the-edge-device/issues/434). | Users pick a model version by hand. |
| 6 | **Alignment drift**: right for a while, then everything wrong; regions of interest offset after a reboot. | About 34 title matches: [#183](https://github.com/jomjol/AI-on-the-edge-device/issues/183), [#1961](https://github.com/jomjol/AI-on-the-edge-device/issues/1961), [#3389](https://github.com/jomjol/AI-on-the-edge-device/issues/3389). | Two alignment marks matched every round. No "alignment failed, skip this round". |
| 7 | **Glare and flash reflections.** | Rarely in titles, common in threads: [#1855](https://github.com/jomjol/AI-on-the-edge-device/issues/1855), [#3130](https://github.com/jomjol/AI-on-the-edge-device/issues/3130). | Hardware only: diffuser, lower LED intensity, external LEDs. |
| 8 | **Memory and crashes** on the ESP32: PSRAM, a memory leak, a model that can't be allocated. | [#1551](https://github.com/jomjol/AI-on-the-edge-device/issues/1551) is the most-commented issue (85); about 43 title matches for "reboot". | Firmware fixes, release by release. |
| 9 | **Wi-Fi drops**; a failed MQTT publish rebooting the device. | About 35 title matches: [#3059](https://github.com/jomjol/AI-on-the-edge-device/issues/3059), [#2186](https://github.com/jomjol/AI-on-the-edge-device/issues/2186). | Shielding, an external antenna, a better power supply. |
| 10 | **SD card wear and failure.** | About 26 title matches: [#73](https://github.com/jomjol/AI-on-the-edge-device/issues/73), [#3459](https://github.com/jomjol/AI-on-the-edge-device/issues/3459). | Fewer writes. |
| 11 | **Firmware updates**: boot loops after OTA, a release that stopped all readings. | About 24 title matches: [#3443](https://github.com/jomjol/AI-on-the-edge-device/issues/3443), [#2945](https://github.com/jomjol/AI-on-the-edge-device/issues/2945). | — |
| 12 | **Home Assistant integration breakage**: deprecated MQTT discovery format. | [#3932](https://github.com/jomjol/AI-on-the-edge-device/issues/3932) (60 comments). | — |

Rows 8–12 are what it costs to run a reading pipeline *on* a €5 microcontroller. Rows 1–7 are about
reading and checking, and they apply to any design.

## What ha-ai-meter-reader already solved, and what it lacked

It moved all of rows 8–12 off the device: the camera is any Home Assistant camera, the reading is a vision
model behind an AI Task entity, the checks run in Home Assistant, and setup is a config flow. The model only
copies digits, marks the ones it can't read with `X` and rates its confidence; the decimal point and every
check are applied in Python. It keeps the last frame as an `image` entity, raises a problem after three
failed readings, has a read-now button and a card, and its tests run on a real Home Assistant core. All of
that is kept.

What it lacked showed up on the field data:

- **Its validator only moves forward and confirms a jump by the next reading.** A camera repeats its
  misreads (the same reflection, the same wheel half turned), so the repeat confirms the misread. Replayed on
  the field data, starting from the true reading, it accepted a +15 L misread at 12:35 on the first day, then
  a +1 m³ one confirmed by its own repeat at 13:10, and stayed there: it **ended 1,031 L too high, with 80 true
  readings rejected as decreases** (Meter Vision 0.1.0 had the same validator).
- No handling of a wheel caught between two numbers beyond "write the lower one" (row 1), and no pointer
  dials (rows 2 and 5).
- The reading is `total_increasing`, so the only way back from a wrong value is a manual correction, and a
  wrong value that gets in is in the long-term statistics for good.

## Lesson → what we do

| Lesson | What Meter Vision does |
| --- | --- |
| A camera repeats its misreads; "confirmed by the next reading" accepts them (AI-on-the-Edge row 3, ha-ai-meter-reader, field data). | The published reading is the **median of the last 5 plausible readings**. A misread only counts while it holds the majority. On the field data the reading never leaves the true range (0 L error, at 5- and at 15-minute rounds), against 1,031 L for the confirm-by-next validator. `tests/test_field_corpus.py` replays it on every change. |
| A validator that can only move forward gets stuck above the meter (row 3). | The median can step back down when a misread stops winning, so the reading sensor is **`total`, not `total_increasing`**: a correction is subtracted from consumption instead of being counted as a meter reset. |
| Rate limits that grow with time let a big misread through after a quiet night (row 3, #643). | The growth gate is measured from the newest plausible reading (the median trails a running meter; measuring from it rejected a meter growing faster than a third of the maximum), grows with the time since then but is **capped at three intervals**. With the default water units (0.3 m³ or 300 L per interval) that stays below the 1 m³ misreads of the field data; what does pass still has to win the median. |
| Force-accepting after a timeout can lock in a wrong value; never accepting leaves it stale for hours (row 3). | Readings rejected above the gate move the reading up only when they keep agreeing for **two hours** (at least 5 of them); the field data's longest misread run was 15 minutes. Never more than a day at the maximum increase. Readings rejected below move it down only to undo such a move, within a day and no lower than where it started: a dropped digit repeated for two hours must not take the reading with it. Meanwhile the problem alert fires, and `set_reading` re-bases with the frame in front of you. A frame identical to the previous one (a frozen camera) is an error, so it can't build such a run. |
| Starting from nothing is fragile with a camera that misreads often (field data: a three-reading start locked onto a cluster of +1 m³ misreads). | The **current reading is required at setup** and fills the window, so even the first readings need a majority. Stored state that can't be read falls back to it. Without either, a full window must agree first, and the wait counts as a failure. |
| Don't fill an uncertain wheel from the previous value (row 1). | The model reports `last_wheel_rolling` and writes the lower number; the reading carries a tolerance of one step. Only a last wheel the model can't read at all is used, and then as a lower bound (last digit 0, ten steps of tolerance). Never above the meter. |
| Transition timing is meter-specific and tuned by trial (row 2). | With a pointer dial, a rolling last wheel and a dial at 0–2 **widen the range** by one wheel step instead of guessing which number is right; the median does the rest. No per-meter transition parameter. |
| A model or rule that silently stops working looks healthy (rows 5, 3). | Every outcome is a state of the *Last result* sensor with the digits and dials read; unreadable dials are logged; three failures in a row raise a problem and a notification. |
| Users couldn't debug a rejection without the image (row 3, #3523). | The frame of every attempt, accepted or not, is the *Last frame* image entity, with the digits read in the card. |
| Glare and alignment are hardware problems software can't fix (rows 6, 7). | A vision model doesn't need alignment marks or regions of interest: it finds the counter in the frame and says when it can't read it. The setup guide covers mounting, angle, diffusing and spiders. |
| Running the pipeline on the microcontroller costs memory, SD cards, Wi-Fi resilience and firmware updates (rows 8–12). | **No firmware of our own.** The camera is any Home Assistant camera: stock ESPHome, an existing AI-on-the-Edge device used only for its snapshot URL, or an IP camera. Updates come through HACS. |
| Keep validator state where it survives. Home Assistant drops the extra attributes of an unavailable entity (field: the template-sensor version of this check). | The window, the pending run and the last answer are kept in Home Assistant's storage (`.storage/meter_vision.<entry>`), not in entity attributes. |
| Don't let dashboards wake the camera. | The frame is captured once per reading and served from memory by the `image` entity; the card never touches the camera. |

## Not done, on purpose

- **No user interface on the camera device.** Its configuration and model management are the main source of
  AI-on-the-Edge's complexity (rows 6, 8, 10, 11). Setup and display live in Home Assistant.
- **No image-quality pre-check yet** (glare or blur detection before calling the model). The model already
  says when a wheel is unreadable, at the cost of one call. Worth revisiting if local models make bad frames
  expensive in time.
- **A crop / region picker in Home Assistant** (send only the counter to the model: fewer tokens, less to be
  confused by) is proposed, not built. It is the one piece of UI that would earn its place.

## Known limits of the check

- A chain of misreads that climbs by no more than the maximum increase per interval and then holds the
  majority looks exactly like a meter in use. The maximum increase is the only defence: set it near the
  meter's real peak.
- A misread repeated for two hours moves the reading up. True readings take it back only if they then
  agree for two hours without interruption, within a day. A camera that keeps glitching (like the one in
  the field data) never gives that, and after a day the way back is closed: `set_reading`, prompted by the
  problem alert, is the fix. Getting into that state needs two hours of one repeated wrong value, which
  the field data never shows.
- A downward run can land anywhere from the start of the last upward move upwards, so its error is bounded
  by the size of that move.

## What the field data does not tell us

The readings in the fixture came from AI-on-the-Edge's neural networks, not from a vision model. The corpus
tests the **validator**: how it copes with a source that is wrong a third of the time, in clusters. How often
a vision model misreads the same meter, and whether a local Qwen-VL is good enough, can only be measured with
frames from the camera, which is the comparison described in the [setup guide](setup-guide.md#comparing-providers-on-your-own-meter).
